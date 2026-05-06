"""Deterministic :class:`IdGeneratorPort` that produces UUID-shaped strings."""

from __future__ import annotations

from src.platform.shared.id_generator_port import IdGeneratorPort


class SequentialIdGenerator(IdGeneratorPort):
    """Generates monotonic UUID-shaped strings for deterministic tests.

    Produces values like ``00000001-0000-0000-0000-000000000000`` that satisfy
    the UUID string format accepted by FastAPI's ``UUID`` path parameters.
    """

    def __init__(self, prefix: str = "00000000") -> None:
        # ``prefix`` is accepted for API parity with other id generators
        # but ignored here so the produced strings stay valid UUIDs.
        del prefix
        self._counter = 0

    def next_id(self) -> str:
        """Return the next UUID-shaped identifier in the sequence."""
        self._counter += 1
        return f"{self._counter:08x}-0000-0000-0000-000000000000"
