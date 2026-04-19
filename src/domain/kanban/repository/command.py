from __future__ import annotations

from typing import Protocol

from src.domain.kanban.models import Board, BoardSummary
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result

DUE_AT_UNSET = object()

class KanbanCommandRepository(Protocol):
    def close(self) -> None: ...

    def create_board(self, title: str) -> BoardSummary: ...

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]: ...

    def delete_board(self, board_id: str) -> Result[None, KanbanError]: ...

    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...

    def save_board(self, board: Board) -> Result[None, KanbanError]: ...

    def get_board_id_for_card(self, card_id: str) -> str | None: ...

    def get_board_id_for_column(self, column_id: str) -> str | None: ...
