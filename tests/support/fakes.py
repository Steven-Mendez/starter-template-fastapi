from __future__ import annotations

from datetime import datetime


class FakeIdGenerator:
    def __init__(self, *ids: str) -> None:
        self._ids = list(ids)
        self._counter = 0

    def next_id(self) -> str:
        if self._ids:
            return self._ids.pop(0)
        self._counter += 1
        return f"00000000-0000-4000-8000-{self._counter:012d}"


class FakeClock:
    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed
