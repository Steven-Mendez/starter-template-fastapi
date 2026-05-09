"""Read model for lightweight Kanban board listings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class BoardSummary:
    """Lightweight board projection for list endpoints (no full aggregate)."""

    id: str
    title: str
    created_at: datetime

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("BoardSummary.created_at must be timezone-aware")
