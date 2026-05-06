"""Command DTO for Kanban patch operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.features.kanban.application.contracts import AppCardPriority


@dataclass(frozen=True, slots=True)
class PatchCardCommand:
    """Sparse update payload for the patch-card use case.

    ``clear_due_at`` is required because the HTTP API needs to tell apart
    "field was omitted" from "field was set to ``null`` to clear the
    due date"; ``due_at=None`` cannot represent both intents on its own.
    """

    card_id: str
    title: str | None = None
    description: str | None = None
    column_id: str | None = None
    position: int | None = None
    priority: AppCardPriority | None = None
    due_at: datetime | None = None
    clear_due_at: bool = False

    def has_changes(self) -> bool:
        """Return ``True`` if at least one field would change persisted state."""
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
