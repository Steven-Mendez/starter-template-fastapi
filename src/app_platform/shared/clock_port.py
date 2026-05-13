"""Clock abstraction used to keep time-dependent use cases testable."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Outbound port that returns the current time.

    Wrapping ``datetime.now`` behind a port lets tests freeze or fast-
    forward time and lets production swap timezones without touching
    business logic.
    """

    def now(self) -> datetime:
        """Current time; implementations must return timezone-aware datetimes."""
        ...
