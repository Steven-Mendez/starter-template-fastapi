from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoardSummary
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.queries.list_boards import ListBoardsQuery, handle_list_boards
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class ListBoardsUseCase:
    query_repository: KanbanQueryRepositoryPort

    def execute(
        self,
        query: ListBoardsQuery,
    ) -> AppResult[list[AppBoardSummary], ApplicationError]:
        return handle_list_boards(repository=self.query_repository, query=query)
