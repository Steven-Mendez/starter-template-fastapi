from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.features.kanban.domain.models.card_priority import CardPriority


@dataclass(slots=True)
class Card:
    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: CardPriority
    due_at: datetime | None

    def apply_patch(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        priority: CardPriority | None = None,
        due_at: datetime | None = None,
        clear_due_at: bool = False,
    ) -> None:
        """Apply sparse updates where ``None`` normally means unchanged.

        ``clear_due_at`` exists because the HTTP API must distinguish an
        omitted due date from an explicit JSON null that clears the field.
        """
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if priority is not None:
            self.priority = priority
        if clear_due_at or due_at is not None:
            self.due_at = due_at
