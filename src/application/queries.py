from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.repository import KanbanQueryRepository
from src.domain.kanban.models import Board, BoardSummary, Card
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result


@dataclass(frozen=True, slots=True)
class HealthCheckQuery:
    pass


@dataclass(frozen=True, slots=True)
class ListBoardsQuery:
    pass


@dataclass(frozen=True, slots=True)
class GetBoardQuery:
    board_id: str


@dataclass(frozen=True, slots=True)
class GetCardQuery:
    card_id: str


@dataclass(slots=True)
class KanbanQueryHandlers:
    repository: KanbanQueryRepository

    def handle_health_check(self, query: HealthCheckQuery) -> bool:
        del query
        return self.repository.is_ready()

    def handle_list_boards(self, query: ListBoardsQuery) -> list[BoardSummary]:
        del query
        return self.repository.list_boards()

    def handle_get_board(self, query: GetBoardQuery) -> Result[Board, KanbanError]:
        return self.repository.get_board(query.board_id)

    def handle_get_card(self, query: GetCardQuery) -> Result[Card, KanbanError]:
        return self.repository.get_card(query.card_id)
