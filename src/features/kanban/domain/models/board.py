from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

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
    id: str
    title: str
    created_at: datetime
    version: int = 0
    columns: list[Column] = field(default_factory=list)

    def rename(self, title: str) -> None:
        self.title = title

    def add_column(self, column: Column) -> None:
        self.columns.append(column)

    def next_column_position(self) -> int:
        return len(self.columns)

    def get_column(self, column_id: str) -> Column | None:
        return next((c for c in self.columns if c.id == column_id), None)

    def find_column_containing_card(self, card_id: str) -> Column | None:
        for column in self.columns:
            if any(card.id == card_id for card in column.cards):
                return column
        return None

    def get_card(self, card_id: str) -> Card | None:
        column = self.find_column_containing_card(card_id)
        if column is None:
            return None
        return next((card for card in column.cards if card.id == card_id), None)

    def delete_column(self, column_id: str) -> Result[None, KanbanError]:
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

        if source_column_id == target_column_id:
            if requested_position is not None:
                source_col.move_card_within(card_id, requested_position)
            return Ok(None)

        card = source_col.extract_card(card_id)
        if not card:
            return Err(KanbanError.CARD_NOT_FOUND)

        target_col.insert_card(card, requested_position)
        return Ok(None)

    def _recalculate_column_positions(self) -> None:
        for i, column in enumerate(self.columns):
            column.position = i
