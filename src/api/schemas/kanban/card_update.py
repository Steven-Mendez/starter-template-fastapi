from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.kanban.models import CardPriority


class CardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    column_id: str | None = None
    position: int | None = Field(default=None, ge=0)
    priority: CardPriority | None = None
    due_at: datetime | None = None
