from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.api.schemas.kanban.card_priority import CardPrioritySchema


class CardRead(BaseModel):
    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: CardPrioritySchema
    due_at: datetime | None
