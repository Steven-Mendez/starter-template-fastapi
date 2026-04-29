from __future__ import annotations

from typing import Protocol

from src.domain.kanban.errors import KanbanError
from src.domain.kanban.models import Board, BoardSummary, Card
from src.domain.shared.result import Result


class KanbanQueryRepositoryPort(Protocol):
    def list_all(self) -> list[BoardSummary]: ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]: ...
