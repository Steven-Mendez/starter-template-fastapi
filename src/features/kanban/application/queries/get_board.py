"""Query DTO for Kanban get board operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetBoardQuery:
    board_id: str
