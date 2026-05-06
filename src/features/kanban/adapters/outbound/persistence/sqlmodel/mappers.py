"""Mapping functions between Kanban domain objects and SQLModel rows."""

from __future__ import annotations

from datetime import datetime, timezone

from src.features.kanban.adapters.outbound.persistence.sqlmodel.models import (
    BoardTable,
    CardTable,
    ColumnTable,
)
from src.features.kanban.domain.models import (
    Board,
    BoardSummary,
    Card,
    CardPriority,
    Column,
)


def _ensure_utc(dt: datetime) -> datetime:
    """Return ``dt`` with UTC tzinfo, attaching it if the value is naive.

    SQLite-backed test fixtures occasionally drop tzinfo on round-trip,
    which would otherwise crash subsequent comparisons against aware
    datetimes coming from the application layer.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def card_table_to_domain(row: CardTable) -> Card:
    """Hydrate a :class:`CardTable` row into the :class:`Card` domain entity."""
    return Card(
        id=row.id,
        column_id=row.column_id,
        title=row.title,
        description=row.description,
        position=row.position,
        priority=CardPriority(row.priority),
        due_at=_ensure_utc(row.due_at) if row.due_at else None,
    )


def column_table_to_domain(row: ColumnTable, cards: list[Card]) -> Column:
    """Hydrate a :class:`ColumnTable` row to a :class:`Column` with its cards."""
    return Column(
        id=row.id,
        board_id=row.board_id,
        title=row.title,
        position=row.position,
        cards=cards,
    )


def board_table_to_domain(row: BoardTable, columns: list[Column]) -> Board:
    """Hydrate a :class:`BoardTable` row and columns into a :class:`Board`."""
    return Board(
        id=row.id,
        title=row.title,
        created_at=_ensure_utc(row.created_at),
        version=row.version,
        columns=columns,
    )


def board_table_to_read_model(row: BoardTable) -> BoardSummary:
    """Project a :class:`BoardTable` row into a :class:`BoardSummary` read model."""
    return BoardSummary(
        id=row.id,
        title=row.title,
        created_at=_ensure_utc(row.created_at),
    )


def card_domain_to_table(card: Card, column_id: str) -> CardTable:
    """Build a fresh :class:`CardTable` row from the domain :class:`Card`."""
    return CardTable(
        id=card.id,
        column_id=column_id,
        title=card.title,
        description=card.description,
        position=card.position,
        priority=card.priority.value,
        due_at=card.due_at,
    )


def column_domain_to_table(column: Column, board_id: str) -> ColumnTable:
    """Build a fresh :class:`ColumnTable` row from the domain :class:`Column`."""
    return ColumnTable(
        id=column.id,
        board_id=board_id,
        title=column.title,
        position=column.position,
    )


def board_domain_to_table(board: Board) -> BoardTable:
    """Build a fresh :class:`BoardTable` row from the :class:`Board` aggregate.

    The version is clamped to at least 1 because newly-created
    aggregates start at 0 in the domain but the database column treats
    1 as the first valid revision.
    """
    return BoardTable(
        id=board.id,
        title=board.title,
        version=board.version if board.version > 0 else 1,
        created_at=board.created_at,
    )
