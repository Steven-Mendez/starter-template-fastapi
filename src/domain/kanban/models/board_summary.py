from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class BoardSummary:
    id: str
    title: str
    created_at: datetime
