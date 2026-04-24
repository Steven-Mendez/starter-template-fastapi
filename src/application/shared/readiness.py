from __future__ import annotations

from typing import Protocol


class ReadinessProbe(Protocol):
    def is_ready(self) -> bool: ...
