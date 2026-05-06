"""Command DTO for Kanban patch operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.features.kanban.application.contracts import AppCardPriority


@dataclass(frozen=True, slots=True)
class PatchCardCommand:
    card_id: str
    title: str | None = None
    description: str | None = None
    column_id: str | None = None
    position: int | None = None
    priority: AppCardPriority | None = None
    due_at: datetime | None = None
    clear_due_at: bool = False

    def has_changes(self) -> bool:
        if self.clear_due_at:
            return True
        return any(
            value is not None
            for value in (
                self.title,
                self.description,
                self.column_id,
                self.position,
                self.priority,
                self.due_at,
            )
        )
