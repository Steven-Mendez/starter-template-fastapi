from __future__ import annotations

from enum import StrEnum

from src.domain.kanban.exceptions import (
    BoardNotFoundError,
    CardNotFoundError,
    ColumnNotFoundError,
    InvalidCardMoveError,
    KanbanDomainError,
)
from src.domain.shared.errors import KanbanError


class ApplicationError(StrEnum):
    """Application-level failures exposed to inbound adapters."""

    BOARD_NOT_FOUND = ("board_not_found", "Board not found")
    COLUMN_NOT_FOUND = ("column_not_found", "Column not found")
    CARD_NOT_FOUND = ("card_not_found", "Card not found")
    INVALID_CARD_MOVE = ("invalid_card_move", "Invalid card move")
    PATCH_NO_CHANGES = (
        "patch_no_changes",
        "At least one field must be provided",
    )
    UNMAPPED_DOMAIN_ERROR = (
        "unmapped_domain_error",
        "Unexpected domain error",
    )

    _detail: str

    def __new__(cls, value: str, detail: str) -> ApplicationError:
        member = str.__new__(cls, value)
        member._value_ = value
        member._detail = detail
        return member

    @property
    def detail(self) -> str:
        return self._detail


_ERROR_MAP = {
    KanbanError.BOARD_NOT_FOUND: ApplicationError.BOARD_NOT_FOUND,
    KanbanError.COLUMN_NOT_FOUND: ApplicationError.COLUMN_NOT_FOUND,
    KanbanError.CARD_NOT_FOUND: ApplicationError.CARD_NOT_FOUND,
    KanbanError.INVALID_CARD_MOVE: ApplicationError.INVALID_CARD_MOVE,
}

_EXCEPTION_ERROR_MAP: dict[type[KanbanDomainError], ApplicationError] = {
    BoardNotFoundError: ApplicationError.BOARD_NOT_FOUND,
    ColumnNotFoundError: ApplicationError.COLUMN_NOT_FOUND,
    CardNotFoundError: ApplicationError.CARD_NOT_FOUND,
    InvalidCardMoveError: ApplicationError.INVALID_CARD_MOVE,
}


def from_domain_error(error: KanbanError) -> ApplicationError:
    return _ERROR_MAP.get(error, ApplicationError.UNMAPPED_DOMAIN_ERROR)


def from_domain_exception(exc: KanbanDomainError) -> ApplicationError:
    return _EXCEPTION_ERROR_MAP.get(type(exc), ApplicationError.UNMAPPED_DOMAIN_ERROR)
