from __future__ import annotations

from typing import Protocol

from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board
from src.platform.shared.result import Result


class KanbanCommandRepositoryPort(Protocol):
    def save(self, board: Board) -> None: ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...

    def remove(self, board_id: str) -> Result[None, KanbanError]: ...
