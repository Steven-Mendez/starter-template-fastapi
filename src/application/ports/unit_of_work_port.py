from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from src.application.ports.kanban_command_repository import KanbanCommandRepositoryPort
from src.application.ports.kanban_lookup_repository import KanbanLookupRepositoryPort


class UnitOfWorkPort(Protocol):
    commands: KanbanCommandRepositoryPort
    lookup: KanbanLookupRepositoryPort

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
