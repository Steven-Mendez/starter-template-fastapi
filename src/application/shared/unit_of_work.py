from __future__ import annotations

from typing import Protocol, Self

from src.domain.kanban.repository.command import KanbanCommandRepository


class UnitOfWork(Protocol):
    kanban: KanbanCommandRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
