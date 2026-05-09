"""Command DTO for Kanban board restore operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RestoreBoardCommand:
    """Input payload for the restore-board use case."""

    board_id: str
    actor_id: UUID | None = None
