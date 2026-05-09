"""Command DTO for Kanban delete operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DeleteBoardCommand:
    """Input payload for the delete-board use case."""

    board_id: str
    actor_id: UUID | None = None
