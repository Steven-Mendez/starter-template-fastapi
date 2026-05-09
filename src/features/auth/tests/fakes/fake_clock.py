"""Controllable in-memory clock for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(slots=True)
class FakeClock:
    """Clock with manual ``advance``/``set`` controls.

    Defaults to a fixed deterministic instant so tests do not depend on
    the wall clock. Always returns timezone-aware UTC datetimes to match
    the rest of the codebase.
    """

    _now: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    )

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta

    def set(self, when: datetime) -> None:
        if when.tzinfo is None:
            raise ValueError("FakeClock requires timezone-aware datetimes")
        self._now = when
