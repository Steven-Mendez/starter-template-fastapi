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
    commands: KanbanCommandRepositoryPort
    lookup: KanbanLookupRepositoryPort

    def __init__(self, engine: Engine):
        self._engine = engine
        self._session: Session | None = None

    def __enter__(self) -> Self:
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
        del exc_val, exc_tb
        if self._session is not None:
            # Use cases can return Err before commit. Roll back any open
            # transaction so partially staged writes never leak out of the UoW.
            if exc_type is not None or self._session.in_transaction():
                self._session.rollback()
            self._session.close()

    def commit(self) -> None:
        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
