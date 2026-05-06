"""Pydantic HTTP schema for Kanban card create payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.features.kanban.adapters.inbound.http.schemas.card_priority import (
    CardPrioritySchema,
)


class CardCreate(BaseModel):
    """Request body for ``POST /api/columns/{id}/cards``."""

    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: CardPrioritySchema = CardPrioritySchema.MEDIUM
    due_at: datetime | None = None
