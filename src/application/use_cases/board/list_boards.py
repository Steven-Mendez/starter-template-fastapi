from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoardSummary
from src.application.contracts.mappers import to_app_board_summary
from src.application.kanban.errors import ApplicationError
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.queries.list_boards import ListBoardsQuery
from src.domain.shared.result import Ok, Result


@dataclass(slots=True)
class ListBoardsUseCase:
    query_repository: KanbanQueryRepositoryPort

    def execute(
        self,
        query: ListBoardsQuery,
    ) -> Result[list[AppBoardSummary], ApplicationError]:
        del query
        return Ok(
            [
                to_app_board_summary(summary)
                for summary in self.query_repository.list_all()
            ]
        )
