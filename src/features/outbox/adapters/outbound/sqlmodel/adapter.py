"""Session-scoped SQLModel implementation of :class:`OutboxPort`.

The adapter borrows a ``Session`` managed by an outer unit-of-work
(typically the feature repository's ``write_transaction()``). It stages
an ``INSERT`` on that session and returns; the outer scope owns the
commit. That is what gives the outbox its atomic guarantee: the row
goes in the same transaction as the business state and is rolled back
with it on failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.models import OutboxMessageTable


@dataclass(slots=True)
class SessionSQLModelOutboxAdapter:
    """Stage an outbox row on the caller's session.

    The adapter MUST NOT commit, flush, or open a new transaction —
    those are the outer unit-of-work's responsibility. The contract
    requires the row to become visible to the relay only if and only
    if the surrounding transaction commits.

    SQLModel-aware producer adapters (e.g. the auth repository) may
    read :attr:`session` to attach their own writes to the same
    transaction. Producer *composition* still depends only on the
    abstract ``OutboxUnitOfWorkPort`` — the ``Session`` never leaks
    above the outbound-adapter ring.
    """

    _session: Session

    @property
    def session(self) -> Session:
        """Return the session backing the writer.

        Exposed for SQLModel-aware producer adapters that need to
        attach their own writes to the same transaction; producer
        composition still depends only on ``OutboxUnitOfWorkPort``.
        """
        return self._session

    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None:
        if available_at is not None and available_at.tzinfo is None:
            raise ValueError("OutboxPort.enqueue: available_at must be timezone-aware")
        row = OutboxMessageTable(
            job_name=job_name,
            payload=dict(payload),
        )
        if available_at is not None:
            row.available_at = available_at
        self._session.add(row)
