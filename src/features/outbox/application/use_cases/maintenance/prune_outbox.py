"""Maintenance use case: prune terminal outbox rows and stale dedup marks.

The relay leaves rows in ``status='delivered'`` (after a successful
dispatch) and ``status='failed'`` (after exhausting the retry budget)
on disk; the handler-side dedup table
``processed_outbox_messages`` grows 1:1 with throughput. Without a
retention policy these tables grow without bound — autovacuum,
backups, and replicas all pay the cost.

This use case sweeps three categories on a schedule:

- ``outbox_messages`` rows where ``status='delivered'`` and
  ``delivered_at < now() - retention_delivered``.
- ``outbox_messages`` rows where ``status='failed'`` and
  ``failed_at < now() - retention_failed``.
- ``processed_outbox_messages`` rows where
  ``processed_at < now() - dedup_retention``. The dedup window is
  pegged to ``2 * retry_max_seconds`` at composition time so by the
  time we delete a mark, the corresponding outbox row has already
  reached a terminal state (delivered or failed) and could not be
  re-dispatched even if the mark vanished.

Each table is processed independently. Each delete runs in its own
short transaction and is bounded to ``batch_size`` rows so a single
prune tick never holds a long transaction or blocks autovacuum. The
loop continues per table until the eligibility set is empty (or a
transient transaction fails, in which case the remaining rows stay
eligible for the next tick).

Return shape is :class:`PruneSummary` — per-table counts deleted —
logged at INFO so operators can confirm the prune is making progress.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app_platform.shared.result import Ok, Result
from features.outbox.application.errors import OutboxError
from features.outbox.application.ports.outbound.outbox_repository_port import (
    OutboxRepositoryPort,
)

_logger = logging.getLogger("features.outbox.prune")

_DeleteCallable = Callable[[], int]


@dataclass(frozen=True, slots=True)
class PruneSummary:
    """Per-table counts emitted by a single :class:`PruneOutbox` tick."""

    delivered_deleted: int
    failed_deleted: int
    processed_marks_deleted: int


@dataclass(slots=True)
class PruneOutbox:
    """Sweep terminal outbox rows and stale dedup marks in bounded batches."""

    _repository: OutboxRepositoryPort

    def execute(
        self,
        *,
        retention_delivered_days: int,
        retention_failed_days: int,
        dedup_retention_seconds: float,
        batch_size: int,
    ) -> Result[PruneSummary, OutboxError]:
        """Delete eligible rows, looping per table until the set is empty.

        Args:
            retention_delivered_days: Delivered-row retention window.
                Rows with ``delivered_at`` older than this are deleted.
            retention_failed_days: Failed-row retention window.
                Rows with ``failed_at`` older than this are deleted.
            dedup_retention_seconds: Dedup-mark retention window
                (typically ``2 * retry_max_seconds``).
            batch_size: Maximum rows deleted per transaction. The use
                case loops until the eligibility set is empty so the
                total deletion is unbounded across iterations even
                when each transaction is small.

        Returns:
            ``Ok(PruneSummary)`` with per-table counts. Errors raised
            by the repository propagate; the relay tick wraps this in
            its own log entry.
        """
        now = datetime.now(UTC)
        delivered_cutoff = now - timedelta(days=retention_delivered_days)
        failed_cutoff = now - timedelta(days=retention_failed_days)
        processed_cutoff = now - timedelta(seconds=dedup_retention_seconds)

        delivered_deleted = self._drain(
            lambda: self._repository.delete_delivered_before(
                cutoff=delivered_cutoff, limit=batch_size
            ),
        )
        failed_deleted = self._drain(
            lambda: self._repository.delete_failed_before(
                cutoff=failed_cutoff, limit=batch_size
            ),
        )
        processed_marks_deleted = self._drain(
            lambda: self._repository.delete_processed_marks_before(
                cutoff=processed_cutoff, limit=batch_size
            ),
        )

        summary = PruneSummary(
            delivered_deleted=delivered_deleted,
            failed_deleted=failed_deleted,
            processed_marks_deleted=processed_marks_deleted,
        )
        _logger.info(
            "event=outbox.prune.tick delivered=%d failed=%d processed_marks=%d",
            summary.delivered_deleted,
            summary.failed_deleted,
            summary.processed_marks_deleted,
        )
        return Ok(summary)

    @staticmethod
    def _drain(delete_one_batch: _DeleteCallable) -> int:
        """Call ``delete_one_batch`` until it returns 0 and sum the counts.

        Each call runs in its own short transaction (the repository
        opens one). A transient failure raises through this loop; any
        rows already deleted in earlier iterations stay deleted and
        the surviving eligible rows are picked up by the next tick.
        """
        total = 0
        while True:
            deleted = delete_one_batch()
            if deleted <= 0:
                return total
            total += deleted
