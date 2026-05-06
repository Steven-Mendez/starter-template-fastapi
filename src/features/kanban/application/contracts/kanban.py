"""Application-facing Kanban DTOs returned by use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AppCardPriority(StrEnum):
    """Application-level mirror of :class:`CardPriority` used in DTOs."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class AppCard:
    """Immutable card projection returned to inbound adapters."""

    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: AppCardPriority
    due_at: datetime | None


@dataclass(frozen=True, slots=True)
class AppColumn:
    """Immutable column projection containing its ordered cards."""

    id: str
    board_id: str
    title: str
    position: int
    cards: list[AppCard] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AppBoard:
    """Immutable board projection returned by full-board read use cases."""

    id: str
    title: str
    created_at: datetime
    columns: list[AppColumn] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AppBoardSummary:
    """Lightweight board projection used by listing endpoints."""

    id: str
    title: str
    created_at: datetime
