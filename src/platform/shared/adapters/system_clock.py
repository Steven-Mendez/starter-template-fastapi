"""System clock adapter that returns timezone-aware UTC timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.platform.shared.clock_port import ClockPort


@dataclass(frozen=True, slots=True)
class SystemClock(ClockPort):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
