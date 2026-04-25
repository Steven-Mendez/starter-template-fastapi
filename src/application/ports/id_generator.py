from __future__ import annotations

from typing import Protocol


class IdGenerator(Protocol):
    def next_id(self) -> str: ...
