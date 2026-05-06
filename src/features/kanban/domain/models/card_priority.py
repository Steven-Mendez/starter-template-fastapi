"""Kanban card priority value object."""

from __future__ import annotations

from enum import StrEnum


class CardPriority(StrEnum):
    """Closed set of priority levels a card can carry."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
