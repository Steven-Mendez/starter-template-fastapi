"""Command DTO for Kanban delete operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeleteBoardCommand:
    """Input payload for the delete-board use case."""

    board_id: str
