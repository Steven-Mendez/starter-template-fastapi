from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoardSummary
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.shared import AppOk, ApplicationError, AppResult


@dataclass(frozen=True, slots=True)
class ListBoardsQuery:
    pass


def handle_list_boards(
    *,
    repository: KanbanQueryRepositoryPort,
    query: ListBoardsQuery,
) -> AppResult[list[AppBoardSummary], ApplicationError]:
    del query
    return AppOk(repository.list_all())
