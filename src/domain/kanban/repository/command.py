from __future__ import annotations

from typing import Protocol

from src.domain.kanban.models import Board, BoardSummary
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result


class KanbanCommandRepository(Protocol):
    def create_board(self, title: str) -> BoardSummary: ...

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]: ...

    def delete_board(self, board_id: str) -> Result[None, KanbanError]: ...

    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...

    def save_board(self, board: Board) -> Result[None, KanbanError]: ...

    def find_board_id_by_card(self, card_id: str) -> str | None: ...

    def find_board_id_by_column(self, column_id: str) -> str | None: ...
