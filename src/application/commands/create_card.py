from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.kanban.models import CardPriority


@dataclass(frozen=True, slots=True)
class CreateCardCommand:
    column_id: str
    title: str
    description: str | None
    priority: CardPriority
    due_at: datetime | None
