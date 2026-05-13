"""Transport-agnostic UnitOfWork seam for outbox producers.

Producer features (e.g. authentication) consume :class:`OutboxUnitOfWorkPort`
to open a transaction that atomically commits their business writes
together with the outbox row that triggers the side effect. The port
exposes only the abstractions producers need (``transaction()`` /
``enqueue``) — concretely, it does NOT mention ``sqlmodel.Session``.

A future Mongo-backed outbox can satisfy the same port (its
``transaction()`` would yield a writer bound to a Mongo session) without
any change to producer composition.

This module deliberately lives in ``application`` so producer
composition modules can depend on it without importing another
feature's composition layer (forbidden by the
``Application ↛ Composition`` Import Linter contract).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, Protocol


class OutboxWriter(Protocol):
    """Stage outbox rows inside an active transaction.

    The writer is yielded by :meth:`OutboxUnitOfWorkPort.transaction`
    and is valid only inside that context. Calls outside the
    surrounding ``with`` block are undefined behaviour.
    """

    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None:
        """Record a pending side effect on the active transaction.

        The implementation MUST stage the row on the same underlying
        transaction the surrounding ``transaction()`` opened, and MUST
        NOT commit or flush on its own. ``available_at`` defaults to
        "now" at the database; when non-``None``, it MUST be
        timezone-aware.
        """
        ...


class OutboxUnitOfWorkPort(Protocol):
    """Open a transaction that yields a session-scoped :class:`OutboxWriter`.

    Producer features call ``with uow.transaction() as writer:`` to
    obtain a writer bound to a fresh transaction. On successful exit,
    the implementation commits; on exception, it rolls back and the
    enqueued rows never become visible to the relay.
    """

    def transaction(self) -> AbstractContextManager[OutboxWriter]:
        """Open a write transaction and yield a writer bound to it."""
        ...


# Re-exported for convenience. ``Iterator`` is the contextmanager-
# protocol return type for adapters implementing ``transaction()`` via
# ``@contextmanager``.
__all__ = ["Iterator", "OutboxUnitOfWorkPort", "OutboxWriter"]
