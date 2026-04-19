from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.kanban.models import CardPriority
from src.domain.kanban.repository import DUE_AT_UNSET


@dataclass(frozen=True, slots=True)
class PatchCardCommand:
    card_id: str
    title: str | None = None
    description: str | None = None
    column_id: str | None = None
    position: int | None = None
    priority: CardPriority | None = None
    due_at: datetime | None | object = DUE_AT_UNSET
