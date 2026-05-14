"""Relay tick: claim pending rows and hand each to ``JobQueuePort``.

The worker schedules this use case to run every
``relay_interval_seconds``. A single execution:

1. Calls :meth:`OutboxRepositoryPort.claim_batch` to atomically grab up
   to ``batch_size`` rows whose ``available_at`` has arrived. The
   repository's claim query uses ``FOR UPDATE SKIP LOCKED`` so two
   workers competing for the same table cannot grab the same row.

2. For each claimed row, opens a per-row writer transaction:
   ``JobQueuePort.enqueue(job_name, payload)`` runs inside it and the
   row is marked ``delivered`` in the same transaction. A crash
   between the enqueue and the commit leaves the row in
   ``status='pending'``, eligible for re-claim. The enqueued payload
   carries the reserved key ``__outbox_message_id`` (the row's UUID);
   handlers MUST be idempotent on it.

3. On a transient enqueue failure, reschedules the row
   (``mark_retry``) with an exponential backoff of
   ``min(retry_base * 2^(attempts-1), retry_max)`` — capped so a
   poison row does not burn its entire retry budget in lockstep at
   30s intervals. Once ``attempts`` would meet ``max_attempts`` the
   row flips to ``failed`` so the relay stops competing for budget on
   a pathological row.

The use case never raises through the relay loop: every per-row
exception is converted into a repository write. That keeps the
recurring task observable (a per-tick report) and prevents one bad
row from crashing the worker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app_platform.observability.tracing import traced
from features.background_jobs.application.ports.job_queue_port import JobQueuePort
from features.outbox.application.ports.outbound.outbox_repository_port import (
    OutboxRepositoryPort,
)

_logger = logging.getLogger("features.outbox.dispatch")

# Reserved payload key the relay injects so handlers can dedup on
# repeated deliveries. Sibling changes layer additional reserved keys
# (e.g. ``__trace`` from ``propagate-trace-context-through-jobs``) on
# top of this one. The ``__*`` prefix is the relay's namespace — the
# handler's original payload keys never start with ``__``.
_OUTBOX_MESSAGE_ID_KEY = "__outbox_message_id"
# Reserved key carrying the W3C trace context captured at enqueue time
# (``traceparent`` + optional ``tracestate``). The job entrypoint
# extracts this carrier and attaches the resulting context around the
# handler call so handler spans become children of the originating
# request's trace.
_TRACE_KEY = "__trace"


@dataclass(frozen=True, slots=True)
class RelayTickReport:
    """Counts emitted by a single relay tick, used for observability."""

    claimed: int
    dispatched: int
    retried: int
    failed: int


@dataclass(slots=True)
class DispatchPending:
    """Drain up to ``batch_size`` pending outbox rows per tick."""

    _repository: OutboxRepositoryPort
    _job_queue: JobQueuePort
    _batch_size: int
    _max_attempts: int
    _worker_id: str
    _retry_base: timedelta
    _retry_max: timedelta

    @traced(
        "outbox.dispatch_pending",
        attrs=lambda self: {"outbox.batch_size": self._batch_size},
    )
    def execute(self) -> RelayTickReport:
        now = datetime.now(UTC)
        claimed = self._repository.claim_batch(
            now=now,
            batch_size=self._batch_size,
            worker_id=self._worker_id,
        )
        if not claimed:
            return RelayTickReport(claimed=0, dispatched=0, retried=0, failed=0)

        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)

        dispatched = 0
        retried = 0
        failed = 0
        for row in claimed:
            # Forward-compat: never strip unknown ``__*`` keys the row
            # may already carry (a sibling change may have added one),
            # and never overwrite an existing ``__outbox_message_id``
            # if a producer somehow already wrote it.
            dispatched_payload = {**row.payload}
            dispatched_payload.setdefault(_OUTBOX_MESSAGE_ID_KEY, str(row.id))
            # Forward the W3C trace carrier captured at enqueue time.
            # Empty rows (no active context at enqueue, or legacy rows
            # persisted before the column existed) skip the injection
            # so the handler-side span starts a fresh trace. An
            # existing ``__trace`` already in the payload (manual
            # re-enqueue, redrive tooling) is preserved verbatim.
            if row.trace_context and _TRACE_KEY not in dispatched_payload:
                dispatched_payload[_TRACE_KEY] = dict(row.trace_context)
            with tracer.start_as_current_span("outbox.dispatch_row") as row_span:
                row_span.set_attribute("outbox.message_id", str(row.id))
                row_span.set_attribute("outbox.handler", row.job_name)
                try:
                    self._job_queue.enqueue(row.job_name, dispatched_payload)
                except Exception as exc:
                    next_attempts = row.attempts + 1
                    if next_attempts >= self._max_attempts:
                        self._repository.mark_failed(
                            row.id,
                            attempts=next_attempts,
                            last_error=repr(exc),
                            failed_at=now,
                        )
                        failed += 1
                        _logger.exception(
                            "event=outbox.dispatch.failed id=%s job=%s attempts=%d",
                            row.id,
                            row.job_name,
                            next_attempts,
                        )
                    else:
                        delay = min(
                            self._retry_base * (2 ** (next_attempts - 1)),
                            self._retry_max,
                        )
                        self._repository.mark_retry(
                            row.id,
                            attempts=next_attempts,
                            last_error=repr(exc),
                            available_at=now + delay,
                        )
                        retried += 1
                        _logger.warning(
                            "event=outbox.dispatch.retry id=%s job=%s attempts=%d",
                            row.id,
                            row.job_name,
                            next_attempts,
                        )
                    continue
                # Per-row commit: marking the row delivered runs in its
                # own transaction (the repository opens one). A crash
                # between the enqueue above and this mark leaves the row
                # in ``status='pending'``; the next tick re-claims and
                # the handler's ``__outbox_message_id`` dedup absorbs
                # the second delivery.
                self._repository.mark_delivered(row.id, delivered_at=now)
                dispatched += 1

        _logger.info(
            "event=outbox.relay.tick claimed=%d dispatched=%d retried=%d failed=%d",
            len(claimed),
            dispatched,
            retried,
            failed,
        )
        return RelayTickReport(
            claimed=len(claimed),
            dispatched=dispatched,
            retried=retried,
            failed=failed,
        )
