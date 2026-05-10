"""Query DTO for Kanban list boards operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ListBoardsQuery:
    """Listing query.

    The ``actor_id`` is required so the use case can ask the
    authorization layer which boards the caller has access to. An
    anonymous request (no actor) returns an empty list.
    """

    actor_id: UUID | None = None
