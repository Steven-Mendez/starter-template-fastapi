"""Domain error codes for Kanban business rule failures."""

from __future__ import annotations

from enum import StrEnum


class KanbanError(StrEnum):
    """Closed enumeration of business-rule failures the Kanban domain can produce.

    Each member carries a short, machine-friendly value (used as the
    ``code`` field in HTTP problem responses) and a human-readable
    ``detail`` accessible via the property.
    """

    BOARD_NOT_FOUND = ("board_not_found", "Board not found")
    COLUMN_NOT_FOUND = ("column_not_found", "Column not found")
    CARD_NOT_FOUND = ("card_not_found", "Card not found")
    INVALID_CARD_MOVE = ("invalid_card_move", "Invalid card move")

    _detail: str

    def __new__(cls, value: str, detail: str) -> KanbanError:
        """Build a ``StrEnum`` member that also carries a ``detail`` attribute."""
        member = str.__new__(cls, value)
        member._value_ = value
        member._detail = detail
        return member

    @property
    def detail(self) -> str:
        """Return the human-readable description for this error."""
        return self._detail
