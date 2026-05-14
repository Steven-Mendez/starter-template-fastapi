"""Outbound port the relay use case calls to manipulate outbox rows.

Two parts:

- :meth:`claim_batch` is the relay's read+lock query. It returns up to
  ``batch_size`` rows whose ``status='pending'`` and
  ``available_at <= now`` are claim-eligible. The implementation uses
  ``FOR UPDATE SKIP LOCKED`` so concurrent relay ticks (running in
  multiple worker replicas) do not double-claim a row, and stamps
  ``locked_at``/``locked_by`` so operators can see which worker is
  mid-flight.

- The mark methods commit the outcome of a dispatch attempt:
  :meth:`mark_delivered` for success, :meth:`mark_retry` for a
  transient failure (increments attempts, advances ``available_at``),
  :meth:`mark_failed` once the per-row retry budget is exhausted. The
  dispatch use case calls :meth:`mark_delivered` per row inside the
  same transaction as the enqueue so a crash between enqueue and
  commit leaves the row visible for re-claim.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from features.outbox.domain.message import OutboxMessage


class OutboxRepositoryPort(Protocol):
    """Engine-scoped operations the relay uses to drain the outbox."""

    def claim_batch(
        self,
        *,
        now: datetime,
        batch_size: int,
        worker_id: str,
    ) -> list[OutboxMessage]:
        """Atomically claim up to ``batch_size`` ready rows.

        Returns the claimed rows after stamping ``locked_at`` /
        ``locked_by`` on each. ``now`` is passed in so tests can drive
        a deterministic clock; production callers pass ``datetime.now``
        in UTC.
        """
        ...

    def mark_delivered(
        self,
        id: UUID,
        *,
        delivered_at: datetime,
    ) -> None:
        """Mark a single row ``status='delivered'``.

        The relay calls this inside the same transaction it used to
        enqueue the row to ``JobQueuePort`` (per-row commit). A crash
        between the enqueue and the commit MUST leave the row in
        ``status='pending'`` so the next tick can re-claim it.
        """
        ...

    def mark_retry(
        self,
        id: UUID,
        *,
        attempts: int,
        last_error: str,
        available_at: datetime,
    ) -> None:
        """Record a transient failure and reschedule the row."""
        ...

    def mark_failed(
        self,
        id: UUID,
        *,
        attempts: int,
        last_error: str,
        failed_at: datetime,
    ) -> None:
        """Mark a row ``status='failed'`` after exhausting retries."""
        ...

    def delete_delivered_before(self, *, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` ``delivered`` rows older than ``cutoff``.

        Returns the row count actually deleted in this transaction.
        Callers loop until the return value is 0 to drain the eligible
        set without ever holding more than ``limit`` rows in a single
        transaction (autovacuum / replica friendly).
        """
        ...

    def delete_failed_before(self, *, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` ``failed`` rows older than ``cutoff``.

        Returns the row count actually deleted in this transaction.
        Callers loop until the return value is 0.
        """
        ...

    def delete_processed_marks_before(self, *, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` dedup marks older than ``cutoff``.

        Operates on ``processed_outbox_messages``. Returns the row count
        actually deleted in this transaction; callers loop until 0.
        """
        ...
