"""Query DTO for Kanban get board operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetBoardQuery:
    """Input payload for the get-board use case."""

    board_id: str
