"""ID generator abstraction used by application use cases."""

from __future__ import annotations

from typing import Protocol


class IdGeneratorPort(Protocol):
    """Outbound port that produces stable identifiers for new aggregates.

    Modeling identifier generation as a port keeps use cases independent
    from any specific ID strategy (UUID, snowflake, hash, ...) and lets
    tests inject a deterministic generator.
    """

    def next_id(self) -> str:
        """Return a fresh, globally unique identifier."""
        ...
