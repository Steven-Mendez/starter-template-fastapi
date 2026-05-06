"""Command DTO for Kanban delete operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeleteColumnCommand:
    """Input payload for the delete-column use case."""

    column_id: str
