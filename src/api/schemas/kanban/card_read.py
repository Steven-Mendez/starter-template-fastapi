from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.domain.kanban.models import CardPriority


class CardRead(BaseModel):
    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: CardPriority
    due_at: datetime | None
