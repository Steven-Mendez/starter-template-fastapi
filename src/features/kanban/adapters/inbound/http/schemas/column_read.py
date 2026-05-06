"""Pydantic HTTP schema for Kanban column read payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.features.kanban.adapters.inbound.http.schemas.card_read import CardRead


class ColumnRead(BaseModel):
    id: str
    board_id: str
    title: str
    position: int
    cards: list[CardRead] = Field(default_factory=list)
