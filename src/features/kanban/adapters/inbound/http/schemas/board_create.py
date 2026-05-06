"""Pydantic HTTP schema for Kanban board create payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BoardCreate(BaseModel):
    """Request body for ``POST /api/boards``."""

    title: str = Field(min_length=1, max_length=500)
