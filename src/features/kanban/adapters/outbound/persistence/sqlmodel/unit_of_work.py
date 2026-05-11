"""SQLModel-backed implementation of the Kanban :class:`UnitOfWorkPort`.

The UoW opens one Session against the kanban engine and binds both the
kanban repository and a session-scoped authorization adapter to it. The
authorization adapter shares the *same* Session, so a relationship write
(e.g., the initial owner tuple from ``CreateBoardUseCase``) commits or
rolls back atomically with the kanban write.

The session-scoped ``UserAuthzVersionPort`` adapter is built through a
factory supplied at composition time. Kanban never imports auth-side
adapter code directly; the closure that wraps the auth-side session
adapter is wired in by ``main.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features.authorization.adapters.outbound.sqlmodel import (
    SessionSQLModelAuthorizationAdapter,
)
from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from src.features.authorization.application.ports.outbound import (
    UserAuthzVersionPort,
)
from src.features.authorization.application.registry import AuthorizationRegistry
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

UserAuthzVersionFactory = Callable[[Session], UserAuthzVersionPort]


class SqlModelUnitOfWork(UnitOfWorkPort):
    """UoW that opens one SQLModel session shared by command, lookup, and authz."""

    commands: KanbanCommandRepositoryPort
    lookup: KanbanLookupRepositoryPort
    authorization: AuthorizationPort

    def __init__(
        self,
        engine: Engine,
        *,
        registry: AuthorizationRegistry,
        user_authz_version_factory: UserAuthzVersionFactory,
    ) -> None:
        """Capture the engine, registry, and version-port factory.

        Session creation is deferred until ``__enter__`` so the UoW is
        cheap to construct and a fresh session is opened on each use.
        """
        self._engine = engine
        self._registry = registry
        self._user_authz_version_factory = user_authz_version_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        """Open a fresh session and bind every collaborator to it."""
        self._session = Session(self._engine, expire_on_commit=False)
        repository = SessionSQLModelKanbanRepository(self._session)
        self.commands = repository
        self.lookup = repository
        self.authorization = SessionSQLModelAuthorizationAdapter(
            self._session,
            self._registry,
            self._user_authz_version_factory(self._session),
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
