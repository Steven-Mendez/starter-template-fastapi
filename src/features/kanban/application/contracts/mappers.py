"""Mapping functions from Kanban domain objects to application DTOs."""

from __future__ import annotations

from src.features.kanban.application.contracts.kanban import (
    AppBoard,
    AppBoardSummary,
    AppCard,
    AppCardPriority,
    AppColumn,
)
from src.features.kanban.domain.models import (
    Board,
    BoardSummary,
    Card,
    CardPriority,
    Column,
)

_PRIORITY_TO_APP = {
    CardPriority.LOW: AppCardPriority.LOW,
    CardPriority.MEDIUM: AppCardPriority.MEDIUM,
    CardPriority.HIGH: AppCardPriority.HIGH,
}

_PRIORITY_TO_DOMAIN = {
    AppCardPriority.LOW: CardPriority.LOW,
    AppCardPriority.MEDIUM: CardPriority.MEDIUM,
    AppCardPriority.HIGH: CardPriority.HIGH,
}


def to_app_priority(priority: CardPriority) -> AppCardPriority:
    """Translate a domain priority into its application-layer equivalent."""
    return _PRIORITY_TO_APP[priority]


def to_domain_priority(priority: AppCardPriority) -> CardPriority:
    """Translate an application priority back into its domain equivalent."""
    return _PRIORITY_TO_DOMAIN[priority]


def to_app_card(card: Card) -> AppCard:
    """Project a domain :class:`Card` into the immutable application DTO."""
    return AppCard(
        id=card.id,
        column_id=card.column_id,
        title=card.title,
        description=card.description,
        position=card.position,
        priority=to_app_priority(card.priority),
        due_at=card.due_at,
    )


def to_app_column(column: Column) -> AppColumn:
    """Project a domain :class:`Column` (and its cards) into the application DTO."""
    return AppColumn(
        id=column.id,
        board_id=column.board_id,
        title=column.title,
        position=column.position,
        cards=[to_app_card(card) for card in column.cards],
    )


def to_app_board(board: Board) -> AppBoard:
    """Project a full domain :class:`Board` aggregate into the application DTO."""
    return AppBoard(
        id=board.id,
        title=board.title,
        created_at=board.created_at,
        columns=[to_app_column(column) for column in board.columns],
    )


def to_app_board_summary(summary: BoardSummary) -> AppBoardSummary:
    """Project a lightweight :class:`BoardSummary` into the application DTO."""
    return AppBoardSummary(
        id=summary.id,
        title=summary.title,
        created_at=summary.created_at,
    )
