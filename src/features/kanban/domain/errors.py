"""Domain error codes for Kanban business rule failures."""

from __future__ import annotations

from enum import StrEnum


class KanbanError(StrEnum):
    BOARD_NOT_FOUND = ("board_not_found", "Board not found")
    COLUMN_NOT_FOUND = ("column_not_found", "Column not found")
    CARD_NOT_FOUND = ("card_not_found", "Card not found")
    INVALID_CARD_MOVE = ("invalid_card_move", "Invalid card move")

    _detail: str

    def __new__(cls, value: str, detail: str) -> KanbanError:
        member = str.__new__(cls, value)
        member._value_ = value
        member._detail = detail
        return member

    @property
    def detail(self) -> str:
        return self._detail
