"""UUID-based ID generator adapter for production use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app_platform.shared.id_generator_port import IdGeneratorPort


@dataclass(frozen=True, slots=True)
class UUIDIdGenerator(IdGeneratorPort):
    """Default :class:`IdGeneratorPort` implementation backed by UUID4."""

    def next_id(self) -> str:
        """Return a freshly generated UUID4 string."""
        return str(uuid.uuid4())
