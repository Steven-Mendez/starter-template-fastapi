"""Query DTO for Kanban list boards operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ListBoardsQuery:
    """Empty payload for listing every board.

    Modeled as a query DTO (instead of a no-arg method call) so future
    pagination or filtering options can be added without changing the
    use-case signature or any of its callers.
    """
