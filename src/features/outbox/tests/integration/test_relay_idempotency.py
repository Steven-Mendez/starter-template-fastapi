"""Idempotency-focused integration tests for the outbox relay.

The relay is at-least-once: a worker crash between
``JobQueuePort.enqueue`` and the per-row ``mark_delivered`` commit can
cause the next tick to re-deliver the row. Handlers MUST dedup on the
reserved ``__outbox_message_id`` payload key.

This module pins two correctness properties end-to-end against a real
Postgres so a regression cannot hide behind a passing unit test:

* A row already in ``delivered`` is NOT re-claimed by a subsequent
  tick (the partial index excludes it).
* A simulated crash (queue raises once after enqueue but before
  ``mark_delivered`` commits) results in exactly *one* effective
  handler invocation thanks to the ``processed_outbox_messages``
  dedup table.
"""

from __future__ import annotations

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
from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.application.use_cases.dispatch_pending import DispatchPending
from features.outbox.composition.handler_dedupe import build_handler_dedupe

pytestmark = pytest.mark.integration


@dataclass(slots=True)
class _RecordingQueue:
    """Stub queue that records every enqueue and can raise on demand."""

    enqueued: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    # When non-empty, raises on the first matching name then forgets it.
    raise_once_on: set[str] = field(default_factory=set)

    def enqueue(self, name: str, payload: dict[str, Any]) -> None:
        # Record the attempt *before* possibly raising — the relay
        # records the side effect before it has a chance to commit
        # the mark, which is exactly the at-least-once window we are
        # protecting against.
        self.enqueued.append((name, dict(payload)))
        if name in self.raise_once_on:
            self.raise_once_on.discard(name)
            raise RuntimeError(f"forced one-shot failure for {name}")

    def enqueue_at(
        self, name: str, payload: dict[str, Any], run_at: datetime
    ) -> None:  # pragma: no cover - not exercised
        raise NotImplementedError


def _make_use_case(
    engine: Engine,
    queue: _RecordingQueue,
    *,
    max_attempts: int = 5,
) -> DispatchPending:
    return DispatchPending(
        _repository=SQLModelOutboxRepository(_engine=engine),
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=max_attempts,
        _worker_id="test-worker",
        _retry_base=timedelta(seconds=30),
        _retry_max=timedelta(seconds=900),
    )


def _seed_pending(engine: Engine, *, job_name: str = "send_email") -> str:
    with Session(engine, expire_on_commit=False) as session:
        SessionSQLModelOutboxAdapter(_session=session).enqueue(
            job_name=job_name, payload={"to": "x@example.com"}
        )
        session.commit()
        row = session.execute(text("SELECT id FROM outbox_messages")).one()
        return str(row.id)


def test_relay_skips_already_delivered(postgres_outbox_engine: Engine) -> None:
    """A row pre-marked ``delivered`` MUST NOT be re-claimed by the relay.

    The partial index on ``status='pending'`` excludes delivered rows,
    so the claim query returns nothing and the relay tick is a no-op.
    Pinning this at the integration tier guards against an accidental
    index drop or a status enum widening that lets a re-fetch slip
    through.
    """
    # Seed a pending row, then flip it to ``delivered`` directly. We
    # intentionally bypass the dispatch path so the assertion is "the
    # relay does nothing" rather than "the relay's success path also
    # marks delivered" — that distinction matters because the latter
    # would still pass if the partial-index filter were dropped.
    row_id = _seed_pending(postgres_outbox_engine)
    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        session.execute(
            text(
                "UPDATE outbox_messages SET status='delivered', "
                "delivered_at=:now WHERE id=:id"
            ),
            {"now": datetime.now(UTC), "id": row_id},
        )
        session.commit()

    queue = _RecordingQueue()
    report = _make_use_case(postgres_outbox_engine, queue).execute()

    assert report.claimed == 0
    assert report.dispatched == 0
    assert queue.enqueued == []


def test_relay_redelivers_after_simulated_crash(
    postgres_outbox_engine: Engine,
) -> None:
    """A crash between enqueue and ``mark_delivered`` re-delivers exactly once.

    The setup forces the first tick to raise *after* the queue records
    the enqueue but *before* the relay can mark the row delivered —
    leaving the row in ``status='pending'`` for the next tick to
    re-claim. The handler-side dedup (``processed_outbox_messages``)
    short-circuits the second invocation so the effective side-effect
    count is exactly one.
    """
    row_id = _seed_pending(postgres_outbox_engine, job_name="boom")

    # First tick: the queue raises after recording the enqueue. The
    # relay reschedules the row (mark_retry) rather than marking it
    # delivered, so the row stays claim-eligible.
    queue = _RecordingQueue(raise_once_on={"boom"})
    first = _make_use_case(postgres_outbox_engine, queue).execute()
    assert first.dispatched == 0
    assert first.retried == 1
    assert len(queue.enqueued) == 1  # first attempt recorded

    # Force the retry window to "now" so the next tick sees the row.
    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        session.execute(
            text("UPDATE outbox_messages SET available_at = :now WHERE id = :id"),
            {"now": datetime.now(UTC), "id": row_id},
        )
        session.commit()

    # Handler-side dedup wired against the same engine. Simulates a
    # real handler that records the message id on first observation
    # and short-circuits on the second.
    dedupe = build_handler_dedupe(postgres_outbox_engine)
    effective_invocations: list[dict[str, Any]] = []

    def _handler_with_dedup(payload: dict[str, Any]) -> None:
        message_id = str(payload["__outbox_message_id"])
        if not dedupe(message_id):
            # Already processed — short-circuit to Ok.
            return
        effective_invocations.append(payload)

    # Simulate "first attempt completed the side effect on the
    # destination but the relay crashed before marking delivered" by
    # invoking the handler once with the first-tick payload.
    _, first_payload = queue.enqueued[0]
    _handler_with_dedup(first_payload)
    assert len(effective_invocations) == 1

    # Second tick: queue succeeds normally; relay enqueues the row
    # again (at-least-once). The handler-side dedup catches it.
    second = _make_use_case(postgres_outbox_engine, queue).execute()
    assert second.dispatched == 1
    assert len(queue.enqueued) == 2

    _, second_payload = queue.enqueued[1]
    assert second_payload["__outbox_message_id"] == first_payload["__outbox_message_id"]
    _handler_with_dedup(second_payload)
    assert len(effective_invocations) == 1, (
        "Handler ran twice; processed_outbox_messages dedup did not engage"
    )

    # The row is now delivered, and exactly one dedup mark exists.
    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        row = session.execute(
            text("SELECT status FROM outbox_messages WHERE id = :id"),
            {"id": row_id},
        ).one()
        marks = session.execute(
            text("SELECT COUNT(*) AS n FROM processed_outbox_messages")
        ).one()
    assert row.status == "delivered"
    assert marks.n == 1
