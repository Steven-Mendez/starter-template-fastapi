from __future__ import annotations

from typing import Protocol


class ClosableResource(Protocol):
    def close(self) -> None: ...
