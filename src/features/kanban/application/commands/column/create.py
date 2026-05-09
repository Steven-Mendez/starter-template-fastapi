"""Command DTO for Kanban create operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateColumnCommand:
    """Input payload for the create-column use case."""

    board_id: str
    title: str
    actor_id: UUID | None = None
