"""Unit-level tests for :class:`DispatchPending`.

The use case is driven against a fake repository + a stub job queue
so the test can pre-load any state and observe every state-write the
relay makes. No DB, no Redis, no testcontainers — those concerns
live in the integration suite under ``tests/integration/``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from features.outbox.application.use_cases.dispatch_pending import (
    DispatchPending,
    RelayTickReport,
)
from features.outbox.domain.message import OutboxMessage

pytestmark = pytest.mark.unit


def _msg(
    *,
    job_name: str = "send_email",
    attempts: int = 0,
    available_at: datetime | None = None,
) -> OutboxMessage:
    return OutboxMessage(
        id=uuid4(),
        job_name=job_name,
        payload={"to": "x@example.com"},
        available_at=available_at or datetime.now(UTC),
        status="pending",
        attempts=attempts,
        last_error=None,
        locked_at=None,
        locked_by=None,
        created_at=datetime.now(UTC),
        dispatched_at=None,
    )


@dataclass(slots=True)
class _FakeRepository:
    ready: list[OutboxMessage] = field(default_factory=list)
    dispatched_calls: list[tuple[list[UUID], datetime]] = field(default_factory=list)
    retry_calls: list[tuple[UUID, int, str, datetime]] = field(default_factory=list)
    failed_calls: list[tuple[UUID, int, str]] = field(default_factory=list)

    def claim_batch(
        self,
        *,
        now: datetime,
        batch_size: int,
        worker_id: str,
    ) -> list[OutboxMessage]:
        batch = self.ready[:batch_size]
        self.ready = self.ready[batch_size:]
        return batch

    def mark_dispatched(self, ids: Iterable[UUID], *, dispatched_at: datetime) -> None:
        self.dispatched_calls.append((list(ids), dispatched_at))

    def mark_retry(
        self,
        id: UUID,
        *,
        attempts: int,
        last_error: str,
        available_at: datetime,
    ) -> None:
        self.retry_calls.append((id, attempts, last_error, available_at))

    def mark_failed(self, id: UUID, *, attempts: int, last_error: str) -> None:
        self.failed_calls.append((id, attempts, last_error))


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
    ) -> None:  # pragma: no cover - not exercised
        raise NotImplementedError


def test_empty_claim_returns_zero_report() -> None:
    repo = _FakeRepository()
    use_case = DispatchPending(
        _repository=repo,
        _job_queue=_StubJobQueue(),
        _batch_size=10,
        _max_attempts=5,
        _worker_id="test",
    )
    report = use_case.execute()
    assert report == RelayTickReport(claimed=0, dispatched=0, retried=0, failed=0)
    assert repo.dispatched_calls == []


def test_successful_dispatch_marks_dispatched_in_one_call() -> None:
    repo = _FakeRepository(ready=[_msg(), _msg(), _msg()])
    queue = _StubJobQueue()
    use_case = DispatchPending(
        _repository=repo,
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=5,
        _worker_id="test",
    )
    report = use_case.execute()
    assert report.claimed == 3
    assert report.dispatched == 3
    assert report.retried == 0
    assert report.failed == 0
    assert len(queue.enqueued) == 3
    assert len(repo.dispatched_calls) == 1
    assert len(repo.dispatched_calls[0][0]) == 3


def test_transient_failure_schedules_retry() -> None:
    repo = _FakeRepository(ready=[_msg(job_name="boom")])
    queue = _StubJobQueue(raise_on={"boom"})
    use_case = DispatchPending(
        _repository=repo,
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=5,
        _worker_id="test",
    )
    report = use_case.execute()
    assert report.retried == 1
    assert report.failed == 0
    assert len(repo.retry_calls) == 1
    _id, attempts, last_error, available_at = repo.retry_calls[0]
    assert attempts == 1
    assert "boom" in last_error
    assert available_at > datetime.now(UTC) + timedelta(seconds=20)


def test_exhausting_attempts_flips_to_failed() -> None:
    repo = _FakeRepository(ready=[_msg(job_name="boom", attempts=4)])
    queue = _StubJobQueue(raise_on={"boom"})
    use_case = DispatchPending(
        _repository=repo,
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=5,
        _worker_id="test",
    )
    report = use_case.execute()
    assert report.retried == 0
    assert report.failed == 1
    assert len(repo.failed_calls) == 1
    assert repo.failed_calls[0][1] == 5  # incremented before the threshold check


def test_mixed_batch_reports_each_outcome() -> None:
    repo = _FakeRepository(
        ready=[
            _msg(job_name="ok"),
            _msg(job_name="bad", attempts=0),
            _msg(job_name="ok2"),
            _msg(job_name="terminal", attempts=4),
        ]
    )
    queue = _StubJobQueue(raise_on={"bad", "terminal"})
    use_case = DispatchPending(
        _repository=repo,
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=5,
        _worker_id="test",
    )
    report = use_case.execute()
    assert report.claimed == 4
    assert report.dispatched == 2
    assert report.retried == 1
    assert report.failed == 1
