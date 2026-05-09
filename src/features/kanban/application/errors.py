"""Application error codes for expected Kanban failures."""

from __future__ import annotations

from enum import StrEnum

from src.features.kanban.domain.errors import KanbanError


class ApplicationError(StrEnum):
    """Closed enumeration of failures returned to inbound adapters as ``Err`` results.

    Mirrors :class:`KanbanError` but extends it with application-only
    cases (``PATCH_NO_CHANGES``, ``UNMAPPED_DOMAIN_ERROR``) so adapters
    only have to translate a single error type into HTTP responses.
    """

    BOARD_NOT_FOUND = ("board_not_found", "Board not found")
    COLUMN_NOT_FOUND = ("column_not_found", "Column not found")
    CARD_NOT_FOUND = ("card_not_found", "Card not found")
    INVALID_CARD_MOVE = ("invalid_card_move", "Invalid card move")
    INVALID_POSITION = ("invalid_position", "Position is out of range")
    PATCH_NO_CHANGES = ("patch_no_changes", "At least one field must be provided")
    STALE_WRITE = (
        "stale_write",
        "The board was modified concurrently; reload and retry",
    )
    UNMAPPED_DOMAIN_ERROR = ("unmapped_domain_error", "Unexpected domain error")

    _detail: str

    def __new__(cls, value: str, detail: str) -> ApplicationError:
        """Build a ``StrEnum`` member that also carries a ``detail`` attribute."""
        member = str.__new__(cls, value)
        member._value_ = value
        member._detail = detail
        return member

    @property
    def detail(self) -> str:
        """Return the human-readable description for this error."""
        return self._detail


_ERROR_MAP = {
    KanbanError.BOARD_NOT_FOUND: ApplicationError.BOARD_NOT_FOUND,
    KanbanError.COLUMN_NOT_FOUND: ApplicationError.COLUMN_NOT_FOUND,
    KanbanError.CARD_NOT_FOUND: ApplicationError.CARD_NOT_FOUND,
    KanbanError.INVALID_CARD_MOVE: ApplicationError.INVALID_CARD_MOVE,
    KanbanError.INVALID_POSITION: ApplicationError.INVALID_POSITION,
}


def from_domain_error(error: KanbanError) -> ApplicationError:
    """Translate a domain ``KanbanError`` into the matching ``ApplicationError``.

    Unknown values fall back to ``UNMAPPED_DOMAIN_ERROR`` so a missing
    mapping fails as a 500-class problem instead of leaking the raw
    domain error to the caller.
    """
    return _ERROR_MAP.get(error, ApplicationError.UNMAPPED_DOMAIN_ERROR)
