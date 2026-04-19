from __future__ import annotations

from types import TracebackType
from typing import Self

from src.application.shared.unit_of_work import UnitOfWork
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, repository: InMemoryKanbanRepository) -> None:
        self.kanban = repository

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
