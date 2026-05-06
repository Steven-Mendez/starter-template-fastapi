"""Command DTO for Kanban create operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateBoardCommand:
    """Input payload for the create-board use case."""

    title: str
