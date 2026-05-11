"""SQLModel-backed implementation of the Kanban :class:`UnitOfWorkPort`.

The UoW opens one Session against the kanban engine and binds both the
kanban repository and a session-scoped authorization adapter to it. The
authorization adapter shares the *same* Session, so a relationship write
(e.g., the initial owner tuple from ``CreateBoardUseCase``) commits or
rolls back atomically with the kanban write.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features.auth.adapters.outbound.authorization.sqlmodel import (
    SessionSQLModelAuthorizationAdapter,
)
from src.features.auth.application.authorization.ports import AuthorizationPort
from src.features.auth.application.authorization.registry import (
    AuthorizationRegistry,
)
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
    """UoW that opens one SQLModel session shared by command, lookup, and authz."""

    commands: KanbanCommandRepositoryPort
    lookup: KanbanLookupRepositoryPort
    authorization: AuthorizationPort

    def __init__(self, engine: Engine, *, registry: AuthorizationRegistry) -> None:
        """Capture the engine and registry; defer session creation until ``__enter__``.

        ``registry`` is forwarded to the session-scoped authorization
        adapter so card/column checks performed inside the unit of work
        can walk to the parent board through registered parent callables.
        """
        self._engine = engine
        self._registry = registry
        self._session: Session | None = None

    def __enter__(self) -> Self:
        """Open a fresh session and bind every collaborator to it."""
        self._session = Session(self._engine, expire_on_commit=False)
        repository = SessionSQLModelKanbanRepository(self._session)
        self.commands = repository
        self.lookup = repository
        self.authorization = SessionSQLModelAuthorizationAdapter(
            self._session, self._registry
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Roll back any uncommitted transaction and close the session."""
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
