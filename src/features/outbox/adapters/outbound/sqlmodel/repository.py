"""Engine-scoped SQLModel implementation of :class:`OutboxRepositoryPort`.

This adapter belongs to the relay running inside the worker process —
it owns its own short transactions, not the producer's. ``claim_batch``
runs the canonical Postgres ``FOR UPDATE SKIP LOCKED`` claim query in
one transaction and the per-row state changes (``mark_delivered``,
``mark_retry``, ``mark_failed``) in independent commits so a slow
``JobQueuePort.enqueue`` does not hold the lock window open longer than
necessary.

The repository is intentionally synchronous: the relay drives ticks one
at a time, and the runtime-agnostic cron descriptor exposes a plain
zero-arg sync callable, so the inner work needs no async machinery.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.models import OutboxMessageTable
from features.outbox.domain.message import OutboxMessage
from features.outbox.domain.status import OutboxStatus


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
                    SELECT id, job_name, payload, trace_context, available_at,
                           status, attempts, last_error, locked_at, locked_by,
                           created_at, delivered_at
                    FROM outbox_messages
                    WHERE status = 'pending' AND available_at <= :now
                    ORDER BY available_at, id
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
                delivered_at=row.delivered_at,
                trace_context=dict(row.trace_context or {}),
            )
            for row in rows
        ]

    def mark_delivered(
        self,
        id: UUID,
        *,
        delivered_at: datetime,
    ) -> None:
        with self._write_session() as session:
            session.execute(
                sa.update(OutboxMessageTable)
                .where(_id_column() == id)
                .values(
                    status="delivered",
                    delivered_at=delivered_at,
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
                .where(_id_column() == id)
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
        failed_at: datetime,
    ) -> None:
        with self._write_session() as session:
            session.execute(
                sa.update(OutboxMessageTable)
                .where(_id_column() == id)
                .values(
                    status="failed",
                    attempts=attempts,
                    last_error=last_error,
                    failed_at=failed_at,
                    locked_at=None,
                    locked_by=None,
                )
            )

    def delete_delivered_before(self, *, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` delivered rows older than ``cutoff``.

        Uses the ``DELETE ... WHERE id IN (SELECT id ... LIMIT)``
        idiom so each transaction touches at most ``limit`` rows —
        bounded enough that autovacuum and replicas keep up even when
        the eligibility set is large. Returns ``rowcount``.
        """
        if limit <= 0:
            return 0
        with self._write_session() as session:
            result = session.execute(
                sa.text(
                    """
                    DELETE FROM outbox_messages
                    WHERE id IN (
                        SELECT id FROM outbox_messages
                        WHERE status = 'delivered'
                          AND delivered_at IS NOT NULL
                          AND delivered_at < :cutoff
                        ORDER BY delivered_at
                        LIMIT :limit
                    )
                    """
                ),
                {"cutoff": cutoff, "limit": limit},
            )
            return int(getattr(result, "rowcount", 0) or 0)

    def delete_failed_before(self, *, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` failed rows older than ``cutoff``."""
        if limit <= 0:
            return 0
        with self._write_session() as session:
            result = session.execute(
                sa.text(
                    """
                    DELETE FROM outbox_messages
                    WHERE id IN (
                        SELECT id FROM outbox_messages
                        WHERE status = 'failed'
                          AND failed_at IS NOT NULL
                          AND failed_at < :cutoff
                        ORDER BY failed_at
                        LIMIT :limit
                    )
                    """
                ),
                {"cutoff": cutoff, "limit": limit},
            )
            return int(getattr(result, "rowcount", 0) or 0)

    def delete_processed_marks_before(self, *, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` dedup marks older than ``cutoff``."""
        if limit <= 0:
            return 0
        with self._write_session() as session:
            result = session.execute(
                sa.text(
                    """
                    DELETE FROM processed_outbox_messages
                    WHERE id IN (
                        SELECT id FROM processed_outbox_messages
                        WHERE processed_at < :cutoff
                        ORDER BY processed_at
                        LIMIT :limit
                    )
                    """
                ),
                {"cutoff": cutoff, "limit": limit},
            )
            return int(getattr(result, "rowcount", 0) or 0)


def _coerce_status(value: str) -> OutboxStatus:
    if value in ("pending", "delivered", "failed"):
        return value  # type: ignore[return-value]
    raise ValueError(f"Unknown outbox status: {value!r}")


def _id_column() -> sa.Column[UUID]:
    """Return the table's ``id`` column for a typed ``WHERE`` expression.

    SQLModel's declarative ``Field`` shape makes ``OutboxMessageTable.id``
    look to mypy like an ``UUID`` value rather than the SQLAlchemy
    column it actually is, so ``OutboxMessageTable.id == id`` types as
    ``bool`` instead of ``ColumnElement[bool]``. Going through
    ``__table__.c`` is the cleanest, type-correct path; the previous
    ``cast(Any, ...)`` workaround stripped real type errors along with
    the noise.
    """
    return OutboxMessageTable.__table__.c.id  # type: ignore[attr-defined,no-any-return]
