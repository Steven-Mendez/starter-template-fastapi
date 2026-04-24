from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.kanban.models.column import Column
from src.domain.shared.errors import KanbanError


@dataclass(slots=True)
class Board:
    id: str
    title: str
    created_at: datetime
    columns: list[Column] = field(default_factory=list)

    def get_column(self, column_id: str) -> Column | None:
        return next((c for c in self.columns if c.id == column_id), None)

    def delete_column(self, column_id: str) -> KanbanError | None:
        column = self.get_column(column_id)
        if column is None:
            return KanbanError.COLUMN_NOT_FOUND

        self.columns.remove(column)
        self._recalculate_column_positions()
        return None

    def move_card(
        self,
        card_id: str,
        source_column_id: str,
        target_column_id: str,
        requested_position: int | None,
    ) -> KanbanError | None:
        source_col = self.get_column(source_column_id)
        target_col = self.get_column(target_column_id)

        if not source_col or not target_col:
            return KanbanError.INVALID_CARD_MOVE

        if source_column_id == target_column_id:
            if requested_position is not None:
                source_col.move_card_within(card_id, requested_position)
            return None

        card = source_col.extract_card(card_id)
        if not card:
            return KanbanError.CARD_NOT_FOUND

        target_col.insert_card(card, requested_position)
        return None

    def _recalculate_column_positions(self) -> None:
        for i, column in enumerate(self.columns):
            column.position = i
