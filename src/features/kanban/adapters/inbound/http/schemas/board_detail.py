"""Pydantic HTTP schema for Kanban board detail payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.features.kanban.adapters.inbound.http.schemas.column_read import ColumnRead


class BoardDetail(BaseModel):
    """Response shape for ``GET /api/boards/{id}`` with the full board hierarchy."""

    id: str
    title: str
    created_at: datetime
    columns: list[ColumnRead] = Field(default_factory=list)
