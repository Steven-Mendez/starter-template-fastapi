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
  :meth:`mark_dispatched` for success, :meth:`mark_retry` for a
  transient failure (increments attempts, advances ``available_at``),
  :meth:`mark_failed` once the per-row retry budget is exhausted.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.features.outbox.domain.message import OutboxMessage


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

    def mark_dispatched(
        self,
        ids: Iterable[UUID],
        *,
        dispatched_at: datetime,
    ) -> None:
        """Mark a batch of rows ``status='dispatched'``."""
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
    ) -> None:
        """Mark a row ``status='failed'`` after exhausting retries."""
        ...
