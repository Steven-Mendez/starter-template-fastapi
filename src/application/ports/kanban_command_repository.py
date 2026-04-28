from __future__ import annotations

from typing import Protocol

from src.domain.kanban.models import Board
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result


class KanbanCommandRepositoryPort(Protocol):
    def save(self, board: Board) -> None: ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...

    def remove(self, board_id: str) -> Result[None, KanbanError]: ...
