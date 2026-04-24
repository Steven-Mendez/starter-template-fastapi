from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import (
    AppBoard,
    AppBoardSummary,
    AppCard,
)
from src.application.contracts.mappers import (
    to_app_board,
    to_app_board_summary,
    to_app_card,
)
from src.application.queries.get_board import GetBoardQuery
from src.application.queries.get_card import GetCardQuery
from src.application.queries.health_check import HealthCheckQuery
from src.application.queries.list_boards import ListBoardsQuery
from src.application.queries.port import KanbanQueryInputPort
from src.application.shared import (
    AppErr,
    ApplicationError,
    AppOk,
    AppResult,
    ReadinessProbe,
)
from src.application.shared.errors import from_domain_error
from src.domain.kanban.repository import KanbanQueryRepositoryPort
from src.domain.shared.result import Err


@dataclass(slots=True)
class KanbanQueryHandlers(KanbanQueryInputPort):
    repository: KanbanQueryRepositoryPort
    readiness: ReadinessProbe

    def handle_health_check(self, query: HealthCheckQuery) -> bool:
        del query
        return self.readiness.is_ready()

    def handle_list_boards(self, query: ListBoardsQuery) -> list[AppBoardSummary]:
        del query
        return [to_app_board_summary(board) for board in self.repository.list_boards()]

    def handle_get_board(
        self,
        query: GetBoardQuery,
    ) -> AppResult[AppBoard, ApplicationError]:
        board_result = self.repository.get_board(query.board_id)
        if isinstance(board_result, Err):
            return AppErr(from_domain_error(board_result.error))
        return AppOk(to_app_board(board_result.value))

    def handle_get_card(
        self,
        query: GetCardQuery,
    ) -> AppResult[AppCard, ApplicationError]:
        board_id = self.repository.find_board_id_by_card(query.card_id)
        if board_id is None:
            return AppErr(ApplicationError.CARD_NOT_FOUND)

        board_result = self.repository.get_board(board_id)
        if isinstance(board_result, Err):
            return AppErr(from_domain_error(board_result.error))

        for column in board_result.value.columns:
            for card in column.cards:
                if card.id == query.card_id:
                    return AppOk(to_app_card(card))
        return AppErr(ApplicationError.CARD_NOT_FOUND)
