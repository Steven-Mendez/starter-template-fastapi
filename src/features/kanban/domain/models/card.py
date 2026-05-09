from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.features.kanban.domain.models.card_priority import CardPriority


@dataclass(slots=True)
class Card:
    """Kanban card entity owned by a single column.

    Attributes:
        id: Stable identifier for the card.
        column_id: Identifier of the owning column.
        title: Required short label.
        description: Optional long-form description.
        position: Index inside the owning column.
        priority: Closed-set priority level.
        due_at: Optional UTC due date.
        created_by: Audit field — actor who created the card.
        updated_by: Audit field — actor who last modified the card.
    """

    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: CardPriority
    due_at: datetime | None
    created_by: UUID | None = None
    updated_by: UUID | None = None

    def __post_init__(self) -> None:
        if self.due_at is not None and self.due_at.tzinfo is None:
            raise ValueError("Card.due_at must be timezone-aware")

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
            if due_at is not None and due_at.tzinfo is None:
                raise ValueError("Card.due_at must be timezone-aware")
            self.due_at = due_at
