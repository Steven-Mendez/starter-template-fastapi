"""Pydantic HTTP schema for Kanban card priority payloads."""

from __future__ import annotations

from enum import StrEnum


class CardPrioritySchema(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
