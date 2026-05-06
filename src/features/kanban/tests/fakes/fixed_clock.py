"""Test support for fixed clock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.platform.shared.clock_port import ClockPort


@dataclass(slots=True)
class FixedClock(ClockPort):
    fixed: datetime = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.fixed
