"""Pydantic HTTP schema for Kanban board update payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BoardUpdate(BaseModel):
    """Request body for ``PATCH /api/boards/{id}``. ``None`` means leave unchanged."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
