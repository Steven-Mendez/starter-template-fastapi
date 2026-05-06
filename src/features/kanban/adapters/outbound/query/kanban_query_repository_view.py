"""Read-only adapter that exposes only the query surface of a full repository."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.ports.outbound.kanban_query_repository import (
    KanbanQueryRepositoryPort,
)
from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board, BoardSummary, Card
from src.platform.shared.result import Result


@dataclass(slots=True)
class KanbanQueryRepositoryView(KanbanQueryRepositoryPort):
    """Read-only facade that hides the write side of an underlying repository.

    Wrapping the production repository ensures consumers that should
    only read (e.g. listing endpoints) cannot accidentally call into a
    write method just because the concrete object happens to expose one.
    """

    _repository: KanbanQueryRepositoryPort

    def list_all(self) -> list[BoardSummary]:
        return self._repository.list_all()

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        return self._repository.find_by_id(board_id)

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]:
        return self._repository.find_card_by_id(card_id)
