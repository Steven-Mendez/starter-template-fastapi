"""ID generator abstraction used by application use cases."""

from __future__ import annotations

from typing import Protocol


class IdGeneratorPort(Protocol):
    def next_id(self) -> str: ...
