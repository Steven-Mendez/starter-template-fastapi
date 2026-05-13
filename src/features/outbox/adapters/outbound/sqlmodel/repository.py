"""Engine-scoped SQLModel implementation of :class:`OutboxRepositoryPort`.

This adapter belongs to the relay running inside the worker process —
it owns its own short transactions, not the producer's. ``claim_batch``
runs the canonical Postgres ``FOR UPDATE SKIP LOCKED`` claim query in
one transaction and the per-row state changes (``mark_dispatched``,
``mark_retry``, ``mark_failed``) in independent commits so a slow
``JobQueuePort.enqueue`` does not hold the lock window open longer than
necessary.

The repository is intentionally synchronous: the relay loop in the
worker drives ticks one at a time, and arq's ``cron_jobs`` API does not
require async functions for the inner work.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features.outbox.adapters.outbound.sqlmodel.models import OutboxMessageTable
from src.features.outbox.domain.message import OutboxMessage
from src.features.outbox.domain.status import OutboxStatus


@dataclass(slots=True)
class SQLModelOutboxRepository:
    """Drain the outbox using ``FOR UPDATE SKIP LOCKED`` claim semantics."""

    _engine: Engine

    @contextmanager
    def _write_session(self) -> Iterator[Session]:
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def claim_batch(
        self,
        *,
        now: datetime,
        batch_size: int,
        worker_id: str,
    ) -> list[OutboxMessage]:
        """Atomically lock and stamp up to ``batch_size`` ready rows.

        The claim and the lock-stamp run in a single transaction so a
        crash mid-claim leaves no half-claimed rows: either the whole
        batch is stamped + visible to the worker, or nothing changes.
        """
        if batch_size <= 0:
            return []
        with self._write_session() as session:
            rows = session.execute(
                sa.text(
                    """
                    SELECT id, job_name, payload, available_at, status,
                           attempts, last_error, locked_at, locked_by,
                           created_at, dispatched_at
                    FROM outbox_messages
                    WHERE status = 'pending' AND available_at <= :now
                    ORDER BY available_at
                    LIMIT :batch_size
                    FOR UPDATE SKIP LOCKED
                    """
                ),
                {"now": now, "batch_size": batch_size},
            ).all()
            if not rows:
                return []
            claimed_ids = [row.id for row in rows]
            session.execute(
                sa.text(
                    """
                    UPDATE outbox_messages
                    SET locked_at = :now, locked_by = :worker_id
                    WHERE id = ANY(:ids)
                    """
                ),
                {"now": now, "worker_id": worker_id, "ids": claimed_ids},
            )
        return [
            OutboxMessage(
                id=row.id,
                job_name=row.job_name,
                payload=dict(row.payload or {}),
                available_at=row.available_at,
                status=_coerce_status(row.status),
                attempts=row.attempts,
                last_error=row.last_error,
                locked_at=now,
                locked_by=worker_id,
                created_at=row.created_at,
                dispatched_at=row.dispatched_at,
            )
            for row in rows
        ]

    def mark_dispatched(
        self,
        ids: Iterable[UUID],
        *,
        dispatched_at: datetime,
    ) -> None:
        id_list = list(ids)
        if not id_list:
            return
        with self._write_session() as session:
            session.execute(
                sa.update(OutboxMessageTable)
                .where(cast(Any, OutboxMessageTable.id).in_(id_list))
                .values(
                    status="dispatched",
                    dispatched_at=dispatched_at,
                    locked_at=None,
                    locked_by=None,
                )
            )

    def mark_retry(
        self,
        id: UUID,
        *,
        attempts: int,
        last_error: str,
        available_at: datetime,
    ) -> None:
        with self._write_session() as session:
            session.execute(
                sa.update(OutboxMessageTable)
                .where(cast(Any, OutboxMessageTable.id == id))
                .values(
                    attempts=attempts,
                    last_error=last_error,
                    available_at=available_at,
                    locked_at=None,
                    locked_by=None,
                )
            )

    def mark_failed(
        self,
        id: UUID,
        *,
        attempts: int,
        last_error: str,
    ) -> None:
        with self._write_session() as session:
            session.execute(
                sa.update(OutboxMessageTable)
                .where(cast(Any, OutboxMessageTable.id == id))
                .values(
                    status="failed",
                    attempts=attempts,
                    last_error=last_error,
                    locked_at=None,
                    locked_by=None,
                )
            )


def _coerce_status(value: str) -> OutboxStatus:
    if value in ("pending", "dispatched", "failed"):
        return value  # type: ignore[return-value]
    raise ValueError(f"Unknown outbox status: {value!r}")
