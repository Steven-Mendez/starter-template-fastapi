"""SQLModel-backed implementation of the Kanban :class:`UnitOfWorkPort`."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features.kanban.adapters.outbound.persistence.sqlmodel.repository import (
    SessionSQLModelKanbanRepository,
)
from src.features.kanban.application.ports.outbound.kanban_command_repository import (
    KanbanCommandRepositoryPort,
)
from src.features.kanban.application.ports.outbound.kanban_lookup_repository import (
    KanbanLookupRepositoryPort,
)
from src.features.kanban.application.ports.outbound.unit_of_work import UnitOfWorkPort


class SqlModelUnitOfWork(UnitOfWorkPort):
    """UoW that opens one SQLModel session shared by command and lookup repos."""

    commands: KanbanCommandRepositoryPort
    lookup: KanbanLookupRepositoryPort

    def __init__(self, engine: Engine):
        """Capture the engine but defer session creation until ``__enter__``."""
        self._engine = engine
        self._session: Session | None = None

    def __enter__(self) -> Self:
        """Open a fresh session and bind both repositories to it."""
        self._session = Session(self._engine, expire_on_commit=False)
        repository = SessionSQLModelKanbanRepository(self._session)
        self.commands = repository
        self.lookup = repository
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Roll back any uncommitted transaction and close the session.

        Use cases may return ``Err`` after staging writes but before
        committing, so any still-open transaction here must be discarded
        to keep partial writes from leaking out of the unit-of-work.
        """
        del exc_val, exc_tb
        if self._session is not None:
            if exc_type is not None or self._session.in_transaction():
                self._session.rollback()
            self._session.close()

    def commit(self) -> None:
        """Flush pending writes and commit if a session is currently open."""
        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        """Discard pending writes for the current session."""
        if self._session is not None:
            self._session.rollback()
