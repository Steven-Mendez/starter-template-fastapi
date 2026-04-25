from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoard
from src.application.contracts.mappers import to_app_board
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.shared import AppErr, ApplicationError, AppOk, AppResult
from src.application.shared.errors import from_domain_error
from src.domain.shared.result import Err


@dataclass(frozen=True, slots=True)
class GetBoardQuery:
    board_id: str


def handle_get_board(
    *,
    repository: KanbanQueryRepositoryPort,
    query: GetBoardQuery,
) -> AppResult[AppBoard, ApplicationError]:
    board_result = repository.find_by_id(query.board_id)
    if isinstance(board_result, Err):
        return AppErr(from_domain_error(board_result.error))
    return AppOk(to_app_board(board_result.value))
