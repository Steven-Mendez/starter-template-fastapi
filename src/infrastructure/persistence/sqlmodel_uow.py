from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.application.shared.unit_of_work import UnitOfWork
from src.infrastructure.persistence.sqlmodel_repository import SQLModelKanbanRepository


class SqlModelUnitOfWork(UnitOfWork):
    def __init__(self, engine: Engine):
        self._engine = engine
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = Session(self._engine, expire_on_commit=False)
        self.kanban = SQLModelKanbanRepository.from_session(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._session is not None:
            if exc_type is not None:
                self._session.rollback()
            self._session.close()

    def commit(self) -> None:
        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
