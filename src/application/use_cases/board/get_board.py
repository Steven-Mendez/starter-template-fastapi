from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoard
from src.application.contracts.mappers import to_app_board
from src.application.kanban.errors import ApplicationError, from_domain_error
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.queries.get_board import GetBoardQuery
from src.domain.shared.result import Err, Ok, Result


@dataclass(slots=True)
class GetBoardUseCase:
    query_repository: KanbanQueryRepositoryPort

    def execute(self, query: GetBoardQuery) -> Result[AppBoard, ApplicationError]:
        board_result = self.query_repository.find_by_id(query.board_id)
        if isinstance(board_result, Err):
            return Err(from_domain_error(board_result.error))
        return Ok(to_app_board(board_result.value))
