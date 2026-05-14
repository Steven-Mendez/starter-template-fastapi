"""Section 4.1: ``DispatchPending`` increments ``app_outbox_dispatched_total``.

Per-row outcomes:

* Each row marked ``delivered`` records exactly one ``result="success"``.
* Each row that exhausts its retry budget and flips to ``failed``
  records exactly one ``result="failure"`` (after the per-row commit).
* Retries (transient failures that have NOT yet exhausted attempts) do
  NOT increment the counter — only terminal outcomes are counted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app_platform.tests.unit.observability._metric_helpers import (
    CounterHarness,
    install_counter,
)
from features.outbox.application.use_cases.dispatch_pending import DispatchPending
from features.outbox.domain.message import OutboxMessage

pytestmark = pytest.mark.unit


def _msg(
    *,
    job_name: str = "send_email",
    attempts: int = 0,
    payload: dict[str, Any] | None = None,
) -> OutboxMessage:
    return OutboxMessage(
        id=uuid4(),
        job_name=job_name,
        payload=dict(payload) if payload is not None else {"to": "x@example.com"},
        available_at=datetime.now(UTC),
        status="pending",
        attempts=attempts,
        last_error=None,
        locked_at=None,
        locked_by=None,
        created_at=datetime.now(UTC),
        delivered_at=None,
        trace_context={},
    )


@dataclass(slots=True)
class _FakeRepository:
    ready: list[OutboxMessage] = field(default_factory=list)
    delivered_calls: list[tuple[UUID, datetime]] = field(default_factory=list)
    retry_calls: list[tuple[UUID, int, str, datetime]] = field(default_factory=list)
    failed_calls: list[tuple[UUID, int, str, datetime]] = field(default_factory=list)

    def claim_batch(
        self, *, now: datetime, batch_size: int, worker_id: str
    ) -> list[OutboxMessage]:
        batch = self.ready[:batch_size]
        self.ready = self.ready[batch_size:]
        return batch

    def mark_delivered(self, id: UUID, *, delivered_at: datetime) -> None:
        self.delivered_calls.append((id, delivered_at))

    def mark_retry(
        self,
        id: UUID,
        *,
        attempts: int,
        last_error: str,
        available_at: datetime,
    ) -> None:
        self.retry_calls.append((id, attempts, last_error, available_at))

    def mark_failed(
        self,
        id: UUID,
        *,
        attempts: int,
        last_error: str,
        failed_at: datetime,
    ) -> None:
        self.failed_calls.append((id, attempts, last_error, failed_at))

    def delete_delivered_before(
        self, *, cutoff: datetime, limit: int
    ) -> int:  # pragma: no cover
        return 0

    def delete_failed_before(
        self, *, cutoff: datetime, limit: int
    ) -> int:  # pragma: no cover
        return 0

    def delete_processed_marks_before(
        self, *, cutoff: datetime, limit: int
    ) -> int:  # pragma: no cover
        return 0


@dataclass(slots=True)
class _StubJobQueue:
    enqueued: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    raise_on: set[str] = field(default_factory=set)

    def enqueue(self, name: str, payload: dict[str, Any]) -> None:
        self.enqueued.append((name, payload))
        if name in self.raise_on:
            raise RuntimeError(f"forced failure for {name}")

    def enqueue_at(
        self, name: str, payload: dict[str, Any], run_at: datetime
    ) -> None:  # pragma: no cover
        raise NotImplementedError


def _make(
    repo: _FakeRepository,
    queue: _StubJobQueue,
    *,
    max_attempts: int = 5,
) -> DispatchPending:
    return DispatchPending(
        _repository=repo,
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=max_attempts,
        _worker_id="metrics-test",
        _retry_base=timedelta(seconds=30),
        _retry_max=timedelta(seconds=900),
    )


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> CounterHarness:
    return install_counter(
        monkeypatch,
        name="app_outbox_dispatched_total",
        attr_name="OUTBOX_DISPATCHED_TOTAL",
        modules=[
            "app_platform.observability.metrics",
            "features.outbox.application.use_cases.dispatch_pending",
        ],
    )


def test_each_successfully_dispatched_row_increments_success_once(
    counter: CounterHarness,
) -> None:
    repo = _FakeRepository(ready=[_msg(), _msg(), _msg()])
    queue = _StubJobQueue()
    _make(repo, queue).execute()

    assert counter.total(result="success") == 3
    assert counter.total(result="failure") == 0


def test_terminal_failure_increments_failure_once_per_row(
    counter: CounterHarness,
) -> None:
    # ``attempts=4`` + ``max_attempts=5`` means the next attempt is the
    # last one; the row flips to failed.
    repo = _FakeRepository(ready=[_msg(job_name="boom", attempts=4)])
    queue = _StubJobQueue(raise_on={"boom"})
    _make(repo, queue, max_attempts=5).execute()

    assert counter.total(result="failure") == 1
    assert counter.total(result="success") == 0
    # And the row hit the terminal failure repository path.
    assert len(repo.failed_calls) == 1


def test_transient_retry_does_not_increment_either_outcome(
    counter: CounterHarness,
) -> None:
    """Retries are still in-flight; the counter only sees terminal outcomes."""
    repo = _FakeRepository(ready=[_msg(job_name="boom", attempts=0)])
    queue = _StubJobQueue(raise_on={"boom"})
    _make(repo, queue, max_attempts=5).execute()

    assert counter.total(result="success") == 0
    assert counter.total(result="failure") == 0
    # Sanity: the row was rescheduled (retried) rather than counted.
    assert len(repo.retry_calls) == 1


def test_mixed_batch_records_per_row_outcomes(counter: CounterHarness) -> None:
    """Mixed: 2 successes + 1 retry (uncounted) + 1 terminal failure."""
    repo = _FakeRepository(
        ready=[
            _msg(job_name="ok"),
            _msg(job_name="bad", attempts=0),  # transient retry
            _msg(job_name="ok2"),
            _msg(job_name="terminal", attempts=4),  # exhausted → failed
        ]
    )
    queue = _StubJobQueue(raise_on={"bad", "terminal"})
    _make(repo, queue, max_attempts=5).execute()

    assert counter.total(result="success") == 2
    assert counter.total(result="failure") == 1


def test_outbox_dispatched_counter_uses_only_result_attribute(
    counter: CounterHarness,
) -> None:
    """4.4 regression: dispatch counter labels must be ``{result}`` only."""
    repo = _FakeRepository(
        ready=[_msg(job_name="ok"), _msg(job_name="terminal", attempts=4)]
    )
    queue = _StubJobQueue(raise_on={"terminal"})
    _make(repo, queue, max_attempts=5).execute()

    for attrs, _ in counter.points():
        assert set(attrs.keys()) == {"result"}, (
            f"outbox counter emitted unexpected label keys: {set(attrs.keys())}"
        )
