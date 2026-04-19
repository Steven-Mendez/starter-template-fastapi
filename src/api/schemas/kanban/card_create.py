from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.kanban.models import CardPriority


class CardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: CardPriority = CardPriority.MEDIUM
    due_at: datetime | None = None
