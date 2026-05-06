"""Pydantic HTTP schema for Kanban board summary payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BoardSummary(BaseModel):
    """Compact response shape used by listing endpoints."""

    id: str
    title: str
    created_at: datetime
