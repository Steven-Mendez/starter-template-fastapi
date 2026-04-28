from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoardSummary
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.domain.kanban.models import Board, Card
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result


@dataclass(slots=True)
class KanbanQueryRepositoryView(KanbanQueryRepositoryPort):
    """Read-only query adapter surface over a full repository."""

    _repository: KanbanQueryRepositoryPort

    def list_all(self) -> list[AppBoardSummary]:
        return self._repository.list_all()

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        return self._repository.find_by_id(board_id)

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]:
        return self._repository.find_card_by_id(card_id)

    def find_board_id_by_card(self, card_id: str) -> str | None:
        return self._repository.find_board_id_by_card(card_id)
