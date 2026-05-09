"""Command DTO for Kanban delete operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DeleteColumnCommand:
    """Input payload for the delete-column use case."""

    column_id: str
    actor_id: UUID | None = None
