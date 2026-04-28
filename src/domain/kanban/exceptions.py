from __future__ import annotations


class KanbanDomainError(Exception):
    """Base error for kanban domain invariant violations."""


class BoardNotFoundError(KanbanDomainError):
    pass


class ColumnNotFoundError(KanbanDomainError):
    pass


class CardNotFoundError(KanbanDomainError):
    pass


class InvalidCardMoveError(KanbanDomainError):
    pass
