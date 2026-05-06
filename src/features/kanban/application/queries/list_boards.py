"""Query DTO for Kanban list boards operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ListBoardsQuery:
    pass
