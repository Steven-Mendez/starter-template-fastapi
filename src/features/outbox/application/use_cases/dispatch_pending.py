"""Relay tick: claim pending rows and hand each to ``JobQueuePort``.

The worker schedules this use case to run every
``relay_interval_seconds``. A single execution:

1. Calls :meth:`OutboxRepositoryPort.claim_batch` to atomically grab up
   to ``batch_size`` rows whose ``available_at`` has arrived. The
   repository's claim query uses ``FOR UPDATE SKIP LOCKED`` so two
   workers competing for the same table cannot grab the same row.

2. For each claimed row, calls ``JobQueuePort.enqueue(job_name,
   payload)``. The job queue is the consumer side of the pattern; it
   stays unchanged. Successful enqueues are aggregated into a single
   :meth:`mark_dispatched` write to amortise per-row commits.

3. On failure, either reschedules the row (``mark_retry``) with the
   configured retry delay, or — once ``attempts`` would exceed
   ``max_attempts`` — flips it to ``failed`` so the relay stops
   competing for budget on a pathological row.

The use case never raises through the relay loop: every per-row
exception is converted into a repository write. That keeps the
recurring task observable (a per-tick report) and prevents one bad
row from crashing the worker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from features.background_jobs.application.ports.job_queue_port import JobQueuePort
from features.outbox.application.ports.outbound.outbox_repository_port import (
    OutboxRepositoryPort,
)

_logger = logging.getLogger("features.outbox.dispatch")

# Retry delay is fixed for the starter — see design.md for the rationale
# (the destination is a local Redis push; exponential backoff does not
# add anything useful here, and a single configurable knob is one knob
# too many for a starter pattern).
_RETRY_DELAY = timedelta(seconds=30)


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
    _retry_delay: timedelta = _RETRY_DELAY

    def execute(self) -> RelayTickReport:
        now = datetime.now(UTC)
        claimed = self._repository.claim_batch(
            now=now,
            batch_size=self._batch_size,
            worker_id=self._worker_id,
        )
        if not claimed:
            return RelayTickReport(claimed=0, dispatched=0, retried=0, failed=0)

        dispatched_ids = []
        retried = 0
        failed = 0
        for row in claimed:
            try:
                self._job_queue.enqueue(row.job_name, row.payload)
            except Exception as exc:
                next_attempts = row.attempts + 1
                if next_attempts >= self._max_attempts:
                    self._repository.mark_failed(
                        row.id,
                        attempts=next_attempts,
                        last_error=repr(exc),
                    )
                    failed += 1
                    _logger.exception(
                        "event=outbox.dispatch.failed id=%s job=%s attempts=%d",
                        row.id,
                        row.job_name,
                        next_attempts,
                    )
                else:
                    self._repository.mark_retry(
                        row.id,
                        attempts=next_attempts,
                        last_error=repr(exc),
                        available_at=now + self._retry_delay,
                    )
                    retried += 1
                    _logger.warning(
                        "event=outbox.dispatch.retry id=%s job=%s attempts=%d",
                        row.id,
                        row.job_name,
                        next_attempts,
                    )
                continue
            dispatched_ids.append(row.id)

        if dispatched_ids:
            self._repository.mark_dispatched(dispatched_ids, dispatched_at=now)

        _logger.info(
            "event=outbox.relay.tick claimed=%d dispatched=%d retried=%d failed=%d",
            len(claimed),
            len(dispatched_ids),
            retried,
            failed,
        )
        return RelayTickReport(
            claimed=len(claimed),
            dispatched=len(dispatched_ids),
            retried=retried,
            failed=failed,
        )
