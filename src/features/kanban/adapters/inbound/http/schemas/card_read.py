"""Pydantic HTTP schema for Kanban card read payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.features.kanban.adapters.inbound.http.schemas.card_priority import (
    CardPrioritySchema,
)


class CardRead(BaseModel):
    """Public projection of a card."""

    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: CardPrioritySchema
    due_at: datetime | None
