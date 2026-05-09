"""Command DTO for Kanban create operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.features.kanban.application.contracts import AppCardPriority


@dataclass(frozen=True, slots=True)
class CreateCardCommand:
    """Input payload for the create-card use case."""

    column_id: str
    title: str
    description: str | None
    priority: AppCardPriority
    due_at: datetime | None
    actor_id: UUID | None = None
