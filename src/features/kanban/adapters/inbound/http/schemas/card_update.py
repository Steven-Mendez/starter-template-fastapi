"""Pydantic HTTP schema for Kanban card update payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.features.kanban.adapters.inbound.http.schemas.card_priority import (
    CardPrioritySchema,
)


class CardUpdate(BaseModel):
    """Request body for ``PATCH /api/cards/{id}``. ``None`` means leave unchanged."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    column_id: UUID | None = None
    position: int | None = Field(default=None, ge=0)
    priority: CardPrioritySchema | None = None
    due_at: datetime | None = None
