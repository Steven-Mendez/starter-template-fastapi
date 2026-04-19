from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.kanban.models.card_priority import CardPriority


@dataclass(slots=True)
class Card:
    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: CardPriority
    due_at: datetime | None
