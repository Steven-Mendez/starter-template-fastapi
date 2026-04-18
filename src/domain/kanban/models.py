from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class CardPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: CardPriority
    due_at: datetime | None


@dataclass(frozen=True, slots=True)
class Column:
    id: str
    board_id: str
    title: str
    position: int
    cards: list[Card] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class BoardSummary:
    id: str
    title: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Board:
    id: str
    title: str
    created_at: datetime
    columns: list[Column] = field(default_factory=list)
