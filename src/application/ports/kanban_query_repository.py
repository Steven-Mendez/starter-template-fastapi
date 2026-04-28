from __future__ import annotations

from typing import Protocol

from src.application.contracts import AppBoardSummary
from src.domain.kanban.models import Board, Card
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result


class KanbanQueryRepositoryPort(Protocol):
    def list_all(self) -> list[AppBoardSummary]: ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]: ...

    def find_board_id_by_card(self, card_id: str) -> str | None: ...
