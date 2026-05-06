"""Outbound port protocol for Kanban kanban command repository persistence behavior."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board
from src.platform.shared.result import Result


class KanbanCommandRepositoryPort(Protocol):
    """Outbound port for write-side persistence of the :class:`Board` aggregate.

    Use cases work exclusively against this protocol so the persistence
    technology (SQLModel, in-memory fakes, ...) can be swapped without
    touching domain or application code.
    """

    def save(self, board: Board) -> None:
        """Persist the aggregate, inserting new rows or updating existing ones."""
        ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        """Load a writable :class:`Board` aggregate, or return ``BOARD_NOT_FOUND``."""
        ...

    def remove(self, board_id: str) -> Result[None, KanbanError]:
        """Delete a board, cascading to its columns and cards."""
        ...
