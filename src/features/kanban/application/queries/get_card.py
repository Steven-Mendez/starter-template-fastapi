"""Query DTO for Kanban get card operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetCardQuery:
    """Input payload for the get-card use case."""

    card_id: str
