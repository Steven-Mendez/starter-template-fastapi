from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.contracts import AppCardPriority


@dataclass(frozen=True, slots=True)
class CreateCardCommand:
    column_id: str
    title: str
    description: str | None
    priority: AppCardPriority
    due_at: datetime | None
