from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.contracts import AppCardPriority


@dataclass(frozen=True, slots=True)
class PatchCardCommand:
    card_id: str
    title: str | None = None
    description: str | None = None
    column_id: str | None = None
    position: int | None = None
    priority: AppCardPriority | None = None
    due_at: datetime | None = None
    due_at_provided: bool = False
