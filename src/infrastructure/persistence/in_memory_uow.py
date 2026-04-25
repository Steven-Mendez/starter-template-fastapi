from __future__ import annotations

from types import TracebackType
from typing import Self

from src.application.ports.kanban_command_repository import KanbanCommandRepositoryPort
from src.application.shared.unit_of_work import UnitOfWork


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, repository: KanbanCommandRepositoryPort) -> None:
        self.kanban = repository

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None
