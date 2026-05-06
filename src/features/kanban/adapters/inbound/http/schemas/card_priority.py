"""Pydantic HTTP schema for Kanban card priority payloads."""

from __future__ import annotations

from enum import StrEnum


class CardPrioritySchema(StrEnum):
    """HTTP mirror of :class:`AppCardPriority` for request and response bodies."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
