"""Outbound port protocol for Kanban kanban lookup repository persistence behavior."""

from __future__ import annotations

from typing import Protocol


class KanbanLookupRepositoryPort(Protocol):
    """Outbound port for cheap parent-board lookups when only an id is on hand.

    Avoids loading the full :class:`Board` aggregate just to discover
    which board a card or column belongs to, which matters for use
    cases that operate on a single child entity.
    """

    def find_board_id_by_card(self, card_id: str) -> str | None:
        """Parent board id for ``card_id``, or ``None`` if the card is missing."""
        ...

    def find_board_id_by_column(self, column_id: str) -> str | None:
        """Parent board id for ``column_id``, or ``None`` if the column is missing."""
        ...
