"""SQLModel implementation of :class:`OutboxUnitOfWorkPort`.

Wraps a SQLAlchemy ``sessionmaker`` (or, equivalently, a callable that
returns a fresh ``Session``). Each call to :meth:`transaction` opens a
new session, yields a writer staging rows on it, and commits on
successful exit (or rolls back on exception).

The writer reuses :class:`SessionSQLModelOutboxAdapter` for the row-
staging logic; this module is the transactional shell that gives
producers a port to depend on without ever importing
``sqlmodel.Session`` themselves.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelOutboxAdapter,
)
from features.outbox.application.ports.outbox_uow_port import OutboxWriter

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class SQLModelOutboxUnitOfWork:
    """Open a SQLModel transaction and yield a session-scoped outbox writer.

    Implements the :class:`OutboxUnitOfWorkPort` Protocol; the adapter
    owns its own session lifecycle so producers never see a ``Session``
    in their public APIs. The yielded writer stages outbox rows on the
    same session as any other writes the producer makes inside the
    ``transaction()`` block.

    Either ``engine`` (preferred — keeps the standard "construct a
    sessionmaker once" pattern) or ``session_factory`` (escape hatch
    for tests that already own a session lifecycle) may be passed.
    """

    _session_factory: SessionFactory

    @classmethod
    def from_engine(cls, engine: Engine) -> SQLModelOutboxUnitOfWork:
        """Build a unit-of-work bound to the given engine."""

        def _factory() -> Session:
            return Session(engine, expire_on_commit=False)

        return cls(_session_factory=_factory)

    @classmethod
    def from_session_factory(
        cls, session_factory: SessionFactory
    ) -> SQLModelOutboxUnitOfWork:
        """Build a unit-of-work that calls ``session_factory()`` per transaction."""
        return cls(_session_factory=session_factory)

    @contextmanager
    def transaction(self) -> Iterator[OutboxWriter]:
        """Open a write transaction and yield a session-scoped writer.

        On clean exit the underlying session is committed; on exception
        the session is rolled back so the staged rows never become
        visible to the relay.
        """
        with self._session_factory() as session:
            try:
                yield SessionSQLModelOutboxAdapter(_session=session)
                session.commit()
            except Exception:
                session.rollback()
                raise
