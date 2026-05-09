"""Board aggregate root and Kanban column/card coordination rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models.column import Column
from src.features.kanban.domain.specifications.card_move import (
    CardMoveCandidate,
    ValidCardMoveSpecification,
)
from src.platform.shared.result import Err, Ok, Result

if TYPE_CHECKING:
    from src.features.kanban.domain.models.card import Card


@dataclass(slots=True)
class Board:
    """Aggregate root that owns columns and orchestrates legal card moves.

    Acts as the consistency boundary for the Kanban domain: callers
    interact only with :class:`Board` methods and never mutate the
    underlying columns or cards directly, so invariants like contiguous
    column positions and card containment are enforced in one place.

    Attributes:
        id: Stable identifier for the board.
        title: Human-readable board name.
        created_at: Creation timestamp (UTC).
        version: Optimistic-lock counter incremented by the persistence
            adapter on every save.
        columns: Ordered list of columns making up the board.
    """

    id: str
    title: str
    created_at: datetime
    version: int = 0
    columns: list[Column] = field(default_factory=list)
    created_by: UUID | None = None
    updated_by: UUID | None = None

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("Board.created_at must be timezone-aware")

    def rename(self, title: str) -> None:
        """Replace the board title in place."""
        self.title = title

    def add_column(self, column: Column) -> None:
        """Append a column to the end of the board."""
        self.columns.append(column)

    def next_column_position(self) -> int:
        """Return the position a new column should take if appended."""
        return len(self.columns)

    def get_column(self, column_id: str) -> Column | None:
        """Return the column with the given id, or ``None`` if absent."""
        return next((c for c in self.columns if c.id == column_id), None)

    def find_column_containing_card(self, card_id: str) -> Column | None:
        """Return the column that currently holds ``card_id``, or ``None``."""
        for column in self.columns:
            if any(card.id == card_id for card in column.cards):
                return column
        return None

    def get_card(self, card_id: str) -> Card | None:
        """Return the card with the given id, searching across all columns."""
        column = self.find_column_containing_card(card_id)
        if column is None:
            return None
        return next((card for card in column.cards if card.id == card_id), None)

    def delete_column(self, column_id: str) -> Result[None, KanbanError]:
        """Remove a column and re-compact the remaining column positions.

        Returns:
            :class:`Ok` on success, or :class:`Err` with
            ``COLUMN_NOT_FOUND`` if no such column exists.
        """
        column = self.get_column(column_id)
        if column is None:
            return Err(KanbanError.COLUMN_NOT_FOUND)

        self.columns.remove(column)
        self._recalculate_column_positions()
        return Ok(None)

    def move_card(
        self,
        card_id: str,
        source_column_id: str,
        target_column_id: str,
        requested_position: int | None,
    ) -> Result[None, KanbanError]:
        """Move a card across (or within) columns, enforcing the move specification.

        The :class:`ValidCardMoveSpecification` ensures the card stays on
        the same board and that the target column actually exists.
        Within-column moves only re-order; cross-column moves transfer
        the card and re-compact positions in both columns.

        Args:
            card_id: Identifier of the card to move.
            source_column_id: Column the card currently belongs to.
            target_column_id: Column the card should end up in.
            requested_position: Optional position inside the target column;
                ``None`` appends to the end.

        Returns:
            :class:`Ok` on success, or :class:`Err` with the appropriate
            :class:`KanbanError` on failure.
        """
        source_col = self.get_column(source_column_id)
        target_col = self.get_column(target_column_id)

        if source_col is None:
            return Err(KanbanError.INVALID_CARD_MOVE)

        if target_col is None:
            return Err(KanbanError.INVALID_CARD_MOVE)

        candidate = CardMoveCandidate(
            target_column_exists=True,
            current_board_id=self.id,
            target_board_id=target_col.board_id,
        )
        if not ValidCardMoveSpecification().is_satisfied_by(candidate):
            return Err(KanbanError.INVALID_CARD_MOVE)

        # Source column must actually contain the card. Without this check,
        # passing a wrong source_column_id silently no-ops (within-column
        # branch) or returns CARD_NOT_FOUND only on the cross-column path.
        if not any(card.id == card_id for card in source_col.cards):
            return Err(KanbanError.CARD_NOT_FOUND)

        # Validate the requested position against the legal insertion range.
        # For within-column moves the card is removed before reinsertion, so
        # the upper bound matches the cross-column case: ``len(target_col.cards)``.
        if requested_position is not None:
            upper_bound = len(target_col.cards)
            if source_column_id == target_column_id:
                upper_bound -= 1  # extracting the card frees one slot
            if requested_position > max(upper_bound, 0):
                return Err(KanbanError.INVALID_POSITION)

        if source_column_id == target_column_id:
            if requested_position is not None:
                source_col.move_card_within(card_id, requested_position)
            return Ok(None)

        card = source_col.extract_card(card_id)
        if not card:
            # Defensive guard; the precondition above should make this unreachable.
            return Err(KanbanError.CARD_NOT_FOUND)

        target_col.insert_card(card, requested_position)
        return Ok(None)

    def _recalculate_column_positions(self) -> None:
        """Renumber columns so positions stay contiguous after a deletion."""
        for i, column in enumerate(self.columns):
            column.position = i
