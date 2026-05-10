"""Outbound port protocol for Kanban kanban query repository persistence behavior."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board, BoardSummary, Card
from src.platform.shared.result import Result


class KanbanQueryRepositoryPort(Protocol):
    """Outbound port for read-only access to Kanban data.

    Kept separate from the command repository so reads can use a
    cheaper, possibly cached or replica-backed path without sharing the
    write transaction lifecycle.
    """

    def list_all(self) -> list[BoardSummary]:
        """Return a lightweight summary for every board, ordered by creation time."""
        ...

    def list_by_ids(self, board_ids: list[str]) -> list[BoardSummary]:
        """Return summaries restricted to ``board_ids``, preserving creation order.

        Used by ``ListBoardsUseCase`` after the authorization layer resolves
        the user's readable boards. An empty input list SHALL return an
        empty list without hitting the database.
        """
        ...

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        """Load a read-only :class:`Board` aggregate, or return ``BOARD_NOT_FOUND``."""
        ...

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]:
        """Load a card directly by id without traversing its parent board."""
        ...
