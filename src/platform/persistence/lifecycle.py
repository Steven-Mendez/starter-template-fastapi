"""Protocol for resources that need explicit shutdown."""

from __future__ import annotations

from typing import Protocol


class ClosableResource(Protocol):
    """Marker for objects that own resources and need explicit release."""

    def close(self) -> None:
        """Release the underlying resource. Implementations should be idempotent."""
        ...
