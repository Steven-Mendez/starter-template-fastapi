from __future__ import annotations

from src.platform.shared.id_generator_port import IdGeneratorPort


class SequentialIdGenerator(IdGeneratorPort):
    """Generates monotonic UUID-shaped strings for deterministic tests.

    Produces values like ``00000001-0000-0000-0000-000000000000`` that satisfy
    the UUID string format accepted by FastAPI's ``UUID`` path parameters.
    """

    def __init__(self, prefix: str = "00000000") -> None:
        del prefix  # parameter accepted for API compatibility, not used in IDs
        self._counter = 0

    def next_id(self) -> str:
        self._counter += 1
        return f"{self._counter:08x}-0000-0000-0000-000000000000"
