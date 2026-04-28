from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoard
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.queries.get_board import GetBoardQuery, handle_get_board
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class GetBoardUseCase:
    query_repository: KanbanQueryRepositoryPort

    def execute(self, query: GetBoardQuery) -> AppResult[AppBoard, ApplicationError]:
        return handle_get_board(repository=self.query_repository, query=query)
