"""Unit-level tests for :class:`DispatchPending`.

The use case is driven against a fake repository + a stub job queue
so the test can pre-load any state and observe every state-write the
relay makes. No DB, no Redis, no testcontainers — those concerns
live in the integration suite under ``tests/integration/``.
"""

from __future__ import annotations

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
    payload: dict[str, Any] | None = None,
    trace_context: dict[str, Any] | None = None,
) -> OutboxMessage:
    return OutboxMessage(
        id=uuid4(),
        job_name=job_name,
        payload=dict(payload) if payload is not None else {"to": "x@example.com"},
        available_at=available_at or datetime.now(UTC),
        status="pending",
        attempts=attempts,
        last_error=None,
        locked_at=None,
        locked_by=None,
        created_at=datetime.now(UTC),
        delivered_at=None,
        trace_context=dict(trace_context) if trace_context is not None else {},
    )


@dataclass(slots=True)
class _FakeRepository:
    ready: list[OutboxMessage] = field(default_factory=list)
    delivered_calls: list[tuple[UUID, datetime]] = field(default_factory=list)
    retry_calls: list[tuple[UUID, int, str, datetime]] = field(default_factory=list)
    failed_calls: list[tuple[UUID, int, str, datetime]] = field(default_factory=list)

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

    # Prune-related methods declared on the port but unused by the
    # dispatch use case. Implemented as no-ops so the structural
    # ``OutboxRepositoryPort`` Protocol stays satisfied.
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
    ) -> None:  # pragma: no cover - not exercised
        raise NotImplementedError


def _make_use_case(
    repo: _FakeRepository,
    queue: _StubJobQueue,
    *,
    max_attempts: int = 5,
    retry_base: timedelta = timedelta(seconds=30),
    retry_max: timedelta = timedelta(seconds=900),
) -> DispatchPending:
    return DispatchPending(
        _repository=repo,
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=max_attempts,
        _worker_id="test",
        _retry_base=retry_base,
        _retry_max=retry_max,
    )


def test_empty_claim_returns_zero_report() -> None:
    repo = _FakeRepository()
    use_case = _make_use_case(repo, _StubJobQueue())
    report = use_case.execute()
    assert report == RelayTickReport(claimed=0, dispatched=0, retried=0, failed=0)
    assert repo.delivered_calls == []


def test_successful_dispatch_marks_each_row_delivered_inline() -> None:
    repo = _FakeRepository(ready=[_msg(), _msg(), _msg()])
    queue = _StubJobQueue()
    use_case = _make_use_case(repo, queue)
    report = use_case.execute()
    assert report.claimed == 3
    assert report.dispatched == 3
    assert report.retried == 0
    assert report.failed == 0
    assert len(queue.enqueued) == 3
    # Per-row mark: one mark_delivered call per row.
    assert len(repo.delivered_calls) == 3


def test_dispatched_payload_carries_outbox_message_id() -> None:
    msg = _msg(payload={"to": "alice@example.com"})
    repo = _FakeRepository(ready=[msg])
    queue = _StubJobQueue()
    use_case = _make_use_case(repo, queue)
    use_case.execute()
    name, payload = queue.enqueued[0]
    assert name == msg.job_name
    assert payload["to"] == "alice@example.com"
    assert payload["__outbox_message_id"] == str(msg.id)


def test_dispatched_payload_preserves_unknown_reserved_keys() -> None:
    # A sibling change may add a reserved key on the producer side; the
    # relay must not strip it. The reserved-key contract is forward-
    # compatible: older relays carry through keys they do not understand.
    msg = _msg(payload={"to": "a@example.com", "__trace": {"traceparent": "abc"}})
    repo = _FakeRepository(ready=[msg])
    queue = _StubJobQueue()
    use_case = _make_use_case(repo, queue)
    use_case.execute()
    _, payload = queue.enqueued[0]
    assert payload["__trace"] == {"traceparent": "abc"}
    assert payload["__outbox_message_id"] == str(msg.id)


def test_existing_outbox_message_id_in_payload_is_not_overwritten() -> None:
    # If a producer somehow already wrote ``__outbox_message_id`` (e.g.
    # manual re-enqueue via tooling), the relay preserves it verbatim.
    pre_existing = "00000000-0000-0000-0000-000000000001"
    msg = _msg(payload={"to": "a@example.com", "__outbox_message_id": pre_existing})
    repo = _FakeRepository(ready=[msg])
    queue = _StubJobQueue()
    use_case = _make_use_case(repo, queue)
    use_case.execute()
    _, payload = queue.enqueued[0]
    assert payload["__outbox_message_id"] == pre_existing


def test_transient_failure_schedules_retry_with_base_backoff() -> None:
    repo = _FakeRepository(ready=[_msg(job_name="boom")])
    queue = _StubJobQueue(raise_on={"boom"})
    use_case = _make_use_case(repo, queue, retry_base=timedelta(seconds=30))
    report = use_case.execute()
    assert report.retried == 1
    assert report.failed == 0
    assert len(repo.retry_calls) == 1
    _id, attempts, last_error, available_at = repo.retry_calls[0]
    assert attempts == 1
    assert "boom" in last_error
    # First retry: delay == retry_base.
    assert available_at > datetime.now(UTC) + timedelta(seconds=20)
    assert available_at < datetime.now(UTC) + timedelta(seconds=40)


def test_failure_on_one_row_does_not_block_subsequent_successes() -> None:
    # Ordering: ok, bad, ok2. The bad row is rescheduled; the surrounding
    # rows are marked delivered in their own per-row transactions.
    rows = [_msg(job_name="ok"), _msg(job_name="bad"), _msg(job_name="ok2")]
    repo = _FakeRepository(ready=rows)
    queue = _StubJobQueue(raise_on={"bad"})
    use_case = _make_use_case(repo, queue)
    report = use_case.execute()
    assert report.dispatched == 2
    assert report.retried == 1
    delivered_ids = {row_id for row_id, _ in repo.delivered_calls}
    assert delivered_ids == {rows[0].id, rows[2].id}
    assert rows[1].id not in delivered_ids
    assert len(repo.retry_calls) == 1
    assert repo.retry_calls[0][0] == rows[1].id


def test_exhausting_attempts_flips_to_failed_with_failed_at() -> None:
    repo = _FakeRepository(ready=[_msg(job_name="boom", attempts=4)])
    queue = _StubJobQueue(raise_on={"boom"})
    use_case = _make_use_case(repo, queue, max_attempts=5)
    report = use_case.execute()
    assert report.retried == 0
    assert report.failed == 1
    assert len(repo.failed_calls) == 1
    _id, attempts, _err, failed_at = repo.failed_calls[0]
    # Incremented to 5 (== max) before the threshold check.
    assert attempts == 5
    assert failed_at <= datetime.now(UTC)


def test_retry_delay_is_exponential_and_capped() -> None:
    base = timedelta(seconds=30)
    cap = timedelta(seconds=900)
    deltas: list[timedelta] = []
    for attempts_so_far in range(7):  # next_attempts will be 1..7
        msg = _msg(job_name="boom", attempts=attempts_so_far)
        repo = _FakeRepository(ready=[msg])
        queue = _StubJobQueue(raise_on={"boom"})
        use_case = _make_use_case(
            repo,
            queue,
            max_attempts=999,  # never trip the failed branch
            retry_base=base,
            retry_max=cap,
        )
        use_case.execute()
        _id, _attempts, _err, available_at = repo.retry_calls[0]
        # Approximate: tick happens "now"; the recorded available_at is
        # ``now + delay`` for the delay computed against ``next_attempts``.
        deltas.append(available_at - datetime.now(UTC))
    # Expected delays (next_attempts = 1..7): 30, 60, 120, 240, 480, 900, 900.
    expected_seconds = [30, 60, 120, 240, 480, 900, 900]
    for actual, expected in zip(deltas, expected_seconds, strict=True):
        assert abs(actual.total_seconds() - expected) < 2.0, (
            f"expected ~{expected}s, got {actual.total_seconds()}s"
        )


def test_dispatched_payload_carries_trace_context_when_populated() -> None:
    """The relay copies ``trace_context`` into the payload under ``__trace``."""
    carrier = {"traceparent": "00-" + "0" * 32 + "-" + "1" * 16 + "-01"}
    msg = _msg(payload={"to": "a@example.com"}, trace_context=carrier)
    repo = _FakeRepository(ready=[msg])
    queue = _StubJobQueue()
    use_case = _make_use_case(repo, queue)
    use_case.execute()
    _, payload = queue.enqueued[0]
    assert payload["__trace"] == carrier
    # ``trace_context`` is *copied* into the payload, not aliased. The
    # relay holds the row briefly and a mutation here must not bleed
    # back into the source dict.
    assert payload["__trace"] is not msg.trace_context


def test_empty_trace_context_does_not_inject_trace_key() -> None:
    """Legacy rows with ``trace_context = {}`` leave the payload untouched."""
    msg = _msg(payload={"to": "a@example.com"}, trace_context={})
    repo = _FakeRepository(ready=[msg])
    queue = _StubJobQueue()
    use_case = _make_use_case(repo, queue)
    use_case.execute()
    _, payload = queue.enqueued[0]
    assert "__trace" not in payload


def test_existing_payload_trace_key_is_not_overwritten() -> None:
    """Producer-set ``__trace`` (manual replay) wins over the row's column."""
    payload_trace = {"traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01"}
    column_trace = {"traceparent": "00-" + "c" * 32 + "-" + "d" * 16 + "-01"}
    msg = _msg(
        payload={"to": "a@example.com", "__trace": payload_trace},
        trace_context=column_trace,
    )
    repo = _FakeRepository(ready=[msg])
    queue = _StubJobQueue()
    use_case = _make_use_case(repo, queue)
    use_case.execute()
    _, payload = queue.enqueued[0]
    assert payload["__trace"] == payload_trace


def test_warn_path_log_capture_contains_no_raw_email_or_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Task 6.7: rendered warn/error lines carry no raw email or token.

    Drives the regression scenario the redaction change is meant to
    prevent: a transient enqueue failure on a payload that carries
    ``to=<raw email>`` and ``token=<single-use>`` must NOT echo
    either value into the rendered log line. The captured log
    snapshot covers both the warn line (retry path) and the error
    line (terminal failure path) — together they exhaust the two
    payload-adjacent log sites in :func:`DispatchPending.execute`.
    """
    import logging as _logging

    raw_email = "alice@example.com"
    raw_token = "single-use-token-abc123"  # test fixture value, not a credential
    payload = {"to": raw_email, "token": raw_token}

    caplog.set_level(_logging.WARNING, logger="features.outbox.dispatch")
    # Retry branch: attempts=0 + max_attempts=5 → warn-line on enqueue fail.
    retry_msg = _msg(job_name="bad-retry", attempts=0, payload=payload)
    # Terminal branch: attempts=4 + max_attempts=5 → exception-line on fail.
    failed_msg = _msg(job_name="bad-terminal", attempts=4, payload=payload)
    repo = _FakeRepository(ready=[retry_msg, failed_msg])
    queue = _StubJobQueue(raise_on={"bad-retry", "bad-terminal"})
    use_case = _make_use_case(repo, queue, max_attempts=5)

    report = use_case.execute()

    # Sanity: both branches actually fired so the assertions below are real.
    assert report.retried == 1
    assert report.failed == 1

    rendered = caplog.text
    # The raw email must NEVER appear in the warn/error lines.
    assert raw_email not in rendered, (
        f"raw email leaked into outbox dispatch log: {rendered!r}"
    )
    # The raw token must NEVER appear in the warn/error lines.
    assert raw_token not in rendered, (
        f"raw token leaked into outbox dispatch log: {rendered!r}"
    )
    # And every per-record getMessage() rendering — defends against a
    # future change that switches to ``extra={"payload": ...}`` without
    # piping the payload through the redaction filter.
    for record in caplog.records:
        message = record.getMessage()
        assert raw_email not in message
        assert raw_token not in message


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
    use_case = _make_use_case(repo, queue, max_attempts=5)
    report = use_case.execute()
    assert report.claimed == 4
    assert report.dispatched == 2
    assert report.retried == 1
    assert report.failed == 1
