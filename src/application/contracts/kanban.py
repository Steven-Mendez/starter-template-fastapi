from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AppCardPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class AppCard:
    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: AppCardPriority
    due_at: datetime | None


@dataclass(frozen=True, slots=True)
class AppColumn:
    id: str
    board_id: str
    title: str
    position: int
    cards: list[AppCard] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AppBoard:
    id: str
    title: str
    created_at: datetime
    columns: list[AppColumn] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AppBoardSummary:
    id: str
    title: str
    created_at: datetime
