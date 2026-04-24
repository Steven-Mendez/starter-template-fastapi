from __future__ import annotations

from typing import Protocol

from src.domain.kanban.models import Board, BoardSummary
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result


class KanbanQueryRepository(Protocol):
    def list_boards(self) -> list[BoardSummary]: ...

    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...

    def find_board_id_by_card(self, card_id: str) -> str | None: ...
