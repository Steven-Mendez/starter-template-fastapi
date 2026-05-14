"""Contract suite for :class:`OutboxPort` implementations.

Runs the same behavioural assertions against the in-memory fake and the
real SQLModel session-scoped adapter. The fake parametrisations are
marked ``unit`` so they run on every ``make test`` invocation; the real
adapter binding requires a Postgres testcontainer and is marked
``integration`` via the ``postgres_outbox_engine`` fixture in
``../integration/conftest.py``, skipping cleanly when Docker is
unavailable.

Each scenario is split into a pure-protocol helper that takes a
``writer`` and ``observe`` callable so the same body runs against both
bindings — the writer either stages on the fake or on a real session,
and the observer either inspects the fake's ``dispatched`` list or
queries the real ``outbox_messages`` table.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelOutboxAdapter,
)
from features.outbox.application.ports.outbox_port import OutboxPort
from features.outbox.tests.fakes.fake_outbox import InMemoryOutboxAdapter


# Each binding yields (adapter, commit, rollback, observe). ``observe`` is
# called *after* a commit and returns the list of "visible" rows shaped as
# (job_name, payload, available_at). For the fake this is the dispatcher's
# capture list; for the real adapter it is a fresh ``SELECT`` against the
# ``outbox_messages`` table — the closest analogue to "what the relay will
# see on its next claim".
@dataclass(slots=True)
class _Binding:
    name: str
    adapter: OutboxPort
    commit: Callable[[], None]
    rollback: Callable[[], None]
    observe_committed: Callable[[], list[tuple[str, dict[str, Any], datetime | None]]]


@contextmanager
def _fake_binding() -> Iterator[_Binding]:
    def _dispatcher(name: str, payload: dict[str, Any]) -> None:
        # The fake's commit fans dispatcher calls out per row; the
        # observer below pulls the post-commit state off ``dispatched``
        # so this hook can stay a no-op and the binding still sees the
        # same shape the real adapter surfaces from the DB.
        del name, payload

    adapter = InMemoryOutboxAdapter(dispatcher=_dispatcher)
    yield _Binding(
        name="fake",
        adapter=adapter,
        commit=adapter.commit,
        rollback=adapter.rollback,
        observe_committed=lambda: list(adapter.dispatched),
    )


@dataclass(slots=True)
class _RealBindingState:
    """Manages a single SQLAlchemy session for one binding lifecycle."""

    session: Session
    committed: bool = False
    rolled_back: bool = False
    # Captured rows from the most recent ``observe_committed`` call.
    rows: list[tuple[str, dict[str, Any], datetime | None]] = field(
        default_factory=list
    )


@contextmanager
def _real_binding(engine: Engine) -> Iterator[_Binding]:
    session = Session(engine, expire_on_commit=False)
    state = _RealBindingState(session=session)
    adapter = SessionSQLModelOutboxAdapter(_session=session)

    def _commit() -> None:
        session.commit()
        state.committed = True

    def _rollback() -> None:
        session.rollback()
        state.rolled_back = True

    def _observe() -> list[tuple[str, dict[str, Any], datetime | None]]:
        # Open a *fresh* session so the read sees only committed state —
        # the same vantage point the relay has when it scans the table.
        with Session(engine, expire_on_commit=False) as reader:
            rows = reader.execute(
                text(
                    "SELECT job_name, payload, available_at "
                    "FROM outbox_messages ORDER BY created_at, id"
                )
            ).all()
        return [(r.job_name, dict(r.payload or {}), r.available_at) for r in rows]

    try:
        yield _Binding(
            name="real",
            adapter=adapter,
            commit=_commit,
            rollback=_rollback,
            observe_committed=_observe,
        )
    finally:
        if not (state.committed or state.rolled_back):
            session.rollback()
        session.close()


# ── Pytest parametrisation ─────────────────────────────────────────────────────

# The real-adapter parametrisation requests the ``postgres_outbox_engine``
# fixture; pytest only resolves it when the test actually depends on it,
# so the fake-only run on machines without Docker is unaffected. The
# integration tier executes both bindings.


@pytest.fixture
def fake_binding() -> Iterator[_Binding]:
    with _fake_binding() as binding:
        yield binding


@pytest.fixture
def real_binding(postgres_outbox_engine: Engine) -> Iterator[_Binding]:
    with _real_binding(postgres_outbox_engine) as binding:
        yield binding


# ── Scenario bodies ────────────────────────────────────────────────────────────


def _scenario_enqueue_then_commit_dispatches_once(binding: _Binding) -> None:
    binding.adapter.enqueue(job_name="send_email", payload={"to": "a@example.com"})
    # Before commit: nothing visible to the relay.
    assert binding.observe_committed() == []
    binding.commit()
    rows = binding.observe_committed()
    assert len(rows) == 1
    job_name, payload, _available_at = rows[0]
    assert job_name == "send_email"
    assert payload == {"to": "a@example.com"}


def _scenario_enqueue_then_rollback_dispatches_nothing(binding: _Binding) -> None:
    binding.adapter.enqueue(job_name="send_email", payload={"to": "a@example.com"})
    binding.rollback()
    # After rollback the row must NEVER become visible to the relay even if
    # we observe much later — the surrounding transaction was cancelled.
    assert binding.observe_committed() == []


def _scenario_naive_available_at_is_rejected(binding: _Binding) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        binding.adapter.enqueue(
            job_name="send_email",
            payload={},
            available_at=datetime.utcnow(),  # noqa: DTZ003 - intentional naive
        )


def _scenario_future_available_at_is_preserved(binding: _Binding) -> None:
    future = datetime.now(UTC) + timedelta(minutes=5)
    binding.adapter.enqueue(job_name="send_email", payload={}, available_at=future)
    binding.commit()
    rows = binding.observe_committed()
    assert len(rows) == 1
    _name, _payload, available_at = rows[0]
    assert available_at is not None
    # The stored value MUST be timezone-aware and equal to the input in
    # absolute terms. Postgres stores ``timestamp with time zone`` as UTC
    # and may surface it with a different (still-equivalent) tzinfo, so
    # compare on instants rather than tzinfo identity.
    assert available_at.tzinfo is not None
    assert available_at == future


def _scenario_multiple_enqueues_commit_together(binding: _Binding) -> None:
    binding.adapter.enqueue(job_name="a", payload={"k": 1})
    binding.adapter.enqueue(job_name="b", payload={"k": 2})
    binding.adapter.enqueue(job_name="c", payload={"k": 3})
    assert binding.observe_committed() == []
    binding.commit()
    rows = binding.observe_committed()
    assert {row[0] for row in rows} == {"a", "b", "c"}


def _scenario_non_utc_timezone_available_at_round_trips(binding: _Binding) -> None:
    """A non-UTC tz-aware datetime survives the round trip as the same instant.

    Producers in deployments running in non-UTC timezones may pass a tz
    other than UTC; the contract is "round-trips correctly", not "is
    UTC". Postgres normalises to UTC internally and the relay only
    reads the instant, so an equivalence comparison is the right
    invariant.
    """
    tz_plus_two = timezone_offset(hours=2)
    at = (datetime.now(UTC) + timedelta(minutes=10)).astimezone(tz_plus_two)
    binding.adapter.enqueue(job_name="send_email", payload={}, available_at=at)
    binding.commit()
    rows = binding.observe_committed()
    assert len(rows) == 1
    _name, _payload, available_at = rows[0]
    assert available_at is not None
    assert available_at == at


def timezone_offset(*, hours: int) -> Any:
    """Return a fixed-offset tzinfo. Inlined helper to avoid extra imports."""
    from datetime import timedelta as _td
    from datetime import timezone as _tz

    return _tz(_td(hours=hours))


# ── Parametrised tests ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_fake_enqueue_then_commit_dispatches_once(fake_binding: _Binding) -> None:
    _scenario_enqueue_then_commit_dispatches_once(fake_binding)


@pytest.mark.integration
def test_real_enqueue_then_commit_dispatches_once(real_binding: _Binding) -> None:
    _scenario_enqueue_then_commit_dispatches_once(real_binding)


@pytest.mark.unit
def test_fake_enqueue_then_rollback_dispatches_nothing(
    fake_binding: _Binding,
) -> None:
    _scenario_enqueue_then_rollback_dispatches_nothing(fake_binding)


@pytest.mark.integration
def test_real_enqueue_then_rollback_dispatches_nothing(
    real_binding: _Binding,
) -> None:
    _scenario_enqueue_then_rollback_dispatches_nothing(real_binding)


@pytest.mark.unit
def test_fake_naive_available_at_is_rejected(fake_binding: _Binding) -> None:
    _scenario_naive_available_at_is_rejected(fake_binding)


@pytest.mark.integration
def test_real_naive_available_at_is_rejected(real_binding: _Binding) -> None:
    _scenario_naive_available_at_is_rejected(real_binding)


@pytest.mark.unit
def test_fake_future_available_at_is_preserved(fake_binding: _Binding) -> None:
    _scenario_future_available_at_is_preserved(fake_binding)


@pytest.mark.integration
def test_real_future_available_at_is_preserved(real_binding: _Binding) -> None:
    _scenario_future_available_at_is_preserved(real_binding)


@pytest.mark.unit
def test_fake_multiple_enqueues_commit_together(fake_binding: _Binding) -> None:
    _scenario_multiple_enqueues_commit_together(fake_binding)


@pytest.mark.integration
def test_real_multiple_enqueues_commit_together(real_binding: _Binding) -> None:
    _scenario_multiple_enqueues_commit_together(real_binding)


@pytest.mark.unit
def test_fake_non_utc_timezone_available_at_round_trips(
    fake_binding: _Binding,
) -> None:
    _scenario_non_utc_timezone_available_at_round_trips(fake_binding)


@pytest.mark.integration
def test_real_non_utc_timezone_available_at_round_trips(
    real_binding: _Binding,
) -> None:
    _scenario_non_utc_timezone_available_at_round_trips(real_binding)
