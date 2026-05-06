"""Protocol for resources that need explicit shutdown."""

from __future__ import annotations

from typing import Protocol


class ClosableResource(Protocol):
    def close(self) -> None: ...
