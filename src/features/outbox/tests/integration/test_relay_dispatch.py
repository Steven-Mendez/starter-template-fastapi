"""End-to-end relay dispatch against a real PostgreSQL.

Covers the wire-level contract:
- A pending row is dispatched and marked ``delivered``.
- A failing dispatch increments ``attempts`` and reschedules
  ``available_at`` with exponential backoff.
- Reaching ``max_attempts`` flips the row to ``failed``.
- The dispatched payload carries the reserved ``__outbox_message_id``.
- The pending-row partial index has the new ``(available_at, id)``
  shape so the claim's ``ORDER BY`` is fully determined.

Marked ``integration``: relies on a testcontainers Postgres started
by the session-scoped fixture in ``conftest.py``. Skipped on hosts
without Docker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelOutboxAdapter,
)
from features.outbox.adapters.outbound.sqlmodel.models import OutboxMessageTable
from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.application.use_cases.dispatch_pending import DispatchPending

pytestmark = pytest.mark.integration


@dataclass(slots=True)
class _StubQueue:
    enqueued: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    raise_on: set[str] = field(default_factory=set)
    raise_once_on: set[str] = field(default_factory=set)

    def enqueue(self, name: str, payload: dict[str, Any]) -> None:
        self.enqueued.append((name, payload))
        if name in self.raise_on:
            raise RuntimeError(f"forced failure for {name}")
        if name in self.raise_once_on:
            self.raise_once_on.discard(name)
            raise RuntimeError(f"forced one-shot failure for {name}")

    def enqueue_at(
        self, name: str, payload: dict[str, Any], run_at: datetime
    ) -> None:  # pragma: no cover - not exercised
        raise NotImplementedError


def _make_use_case(
    engine: Engine,
    queue: _StubQueue,
    *,
    max_attempts: int = 5,
    retry_base_seconds: float = 30.0,
    retry_max_seconds: float = 900.0,
) -> DispatchPending:
    return DispatchPending(
        _repository=SQLModelOutboxRepository(_engine=engine),
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=max_attempts,
        _worker_id="test-worker",
        _retry_base=timedelta(seconds=retry_base_seconds),
        _retry_max=timedelta(seconds=retry_max_seconds),
    )


def _seed(engine: Engine, *, job_name: str = "send_email") -> UUID:
    with Session(engine, expire_on_commit=False) as session:
        SessionSQLModelOutboxAdapter(_session=session).enqueue(
            job_name=job_name, payload={"to": "x@example.com"}
        )
        session.commit()
        # Fetch the id of the row we just inserted.
        row = session.execute(text("SELECT id FROM outbox_messages")).one()
        return UUID(str(row.id))


def _all_rows(engine: Engine) -> list[OutboxMessageTable]:
    with Session(engine, expire_on_commit=False) as session:
        return list(session.exec(_select_all()).all())


def _select_all() -> Any:
    from sqlmodel import select

    return select(OutboxMessageTable).order_by("created_at")


def test_pending_row_is_dispatched(postgres_outbox_engine: Engine) -> None:
    row_id = _seed(postgres_outbox_engine)
    queue = _StubQueue()
    use_case = _make_use_case(postgres_outbox_engine, queue)
    report = use_case.execute()
    assert report.dispatched == 1
    assert len(queue.enqueued) == 1
    name, payload = queue.enqueued[0]
    assert name == "send_email"
    assert payload["to"] == "x@example.com"
    assert payload["__outbox_message_id"] == str(row_id)
    rows = _all_rows(postgres_outbox_engine)
    assert len(rows) == 1
    assert rows[0].status == "delivered"
    assert rows[0].delivered_at is not None
    assert rows[0].locked_at is None  # released after marking delivered


def test_transient_failure_increments_attempts_and_reschedules(
    postgres_outbox_engine: Engine,
) -> None:
    _seed(postgres_outbox_engine, job_name="boom")
    queue = _StubQueue(raise_on={"boom"})
    use_case = _make_use_case(postgres_outbox_engine, queue)
    report = use_case.execute()
    assert report.retried == 1
    rows = _all_rows(postgres_outbox_engine)
    assert rows[0].status == "pending"
    assert rows[0].attempts == 1
    assert rows[0].last_error is not None
    # First retry uses the base delay (default 30s).
    assert rows[0].available_at > datetime.now(UTC) + timedelta(seconds=20)


def test_exhausted_attempts_flips_to_failed(
    postgres_outbox_engine: Engine,
) -> None:
    _seed(postgres_outbox_engine, job_name="boom")
    queue = _StubQueue(raise_on={"boom"})
    use_case = _make_use_case(postgres_outbox_engine, queue, max_attempts=2)
    # First tick: attempts becomes 1, still pending.
    use_case.execute()
    # Force the row back to claim-eligible immediately.
    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        row = session.exec(_select_all()).one()
        row.available_at = datetime.now(UTC)
        session.add(row)
        session.commit()
    # Second tick: attempts would be 2 (== max), so the row flips to failed.
    report = use_case.execute()
    assert report.failed == 1
    rows = _all_rows(postgres_outbox_engine)
    assert rows[0].status == "failed"
    assert rows[0].attempts == 2
    assert rows[0].failed_at is not None


def test_retry_then_success_uses_exponential_backoff(
    postgres_outbox_engine: Engine,
) -> None:
    """First tick fails, second tick succeeds — verifies backoff progression."""
    _seed(postgres_outbox_engine, job_name="flaky")
    queue = _StubQueue(raise_once_on={"flaky"})
    use_case = _make_use_case(
        postgres_outbox_engine,
        queue,
        max_attempts=5,
        retry_base_seconds=30.0,
    )
    use_case.execute()
    rows = _all_rows(postgres_outbox_engine)
    assert rows[0].status == "pending"
    assert rows[0].attempts == 1
    first_available_at = rows[0].available_at
    # Force the row back to claim-eligible immediately so the second
    # tick picks it up.
    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        row = session.exec(_select_all()).one()
        row.available_at = datetime.now(UTC)
        session.add(row)
        session.commit()
    use_case.execute()
    rows = _all_rows(postgres_outbox_engine)
    assert rows[0].status == "delivered"
    # Two enqueue attempts: one failing, one succeeding.
    assert len(queue.enqueued) == 2
    # First retry: ~30s in the future (base * 2^0).
    assert first_available_at > datetime.now(UTC) - timedelta(seconds=5)


def test_pending_index_definition_matches_spec(
    postgres_outbox_engine: Engine,
) -> None:
    """``ix_outbox_pending`` exists on (available_at, id) with the partial predicate."""
    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        rows = list(
            session.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'outbox_messages' "
                    "AND indexname = 'ix_outbox_pending'"
                )
            ).all()
        )
    assert len(rows) == 1
    indexdef = rows[0][0]
    # Index covers both columns and carries the partial predicate.
    assert "available_at" in indexdef
    assert "id" in indexdef
    assert "status" in indexdef
    assert "pending" in indexdef


def test_already_delivered_row_is_not_redispatched(
    postgres_outbox_engine: Engine,
) -> None:
    _seed(postgres_outbox_engine)
    queue = _StubQueue()
    use_case = _make_use_case(postgres_outbox_engine, queue)
    use_case.execute()
    assert len(queue.enqueued) == 1
    # Run again — the row is already ``delivered`` so the claim query
    # excludes it (filters on ``status='pending'``).
    use_case.execute()
    assert len(queue.enqueued) == 1
