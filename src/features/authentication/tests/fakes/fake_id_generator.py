"""Deterministic UUID generator for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(slots=True)
class FakeIdGenerator:
    """Yields a predictable sequence of UUIDs.

    Each call to ``next_uuid`` produces ``UUID(int=base + counter)`` so
    test assertions can reference deterministic IDs.
    """

    _counter: int = field(default=0)
    _base: int = field(default=0)

    def next_uuid(self) -> UUID:
        self._counter += 1
        return UUID(int=self._base + self._counter)

    def next_id(self) -> str:
        return str(self.next_uuid())

    def reset(self) -> None:
        self._counter = 0
