"""Protocol for dependencies that can report readiness."""

from __future__ import annotations

from typing import Protocol


class ReadinessProbe(Protocol):
    """Outbound port used by health checks to query the readiness of a dependency."""

    def is_ready(self) -> bool:
        """Return ``True`` only when the underlying dependency is fully usable."""
        ...
