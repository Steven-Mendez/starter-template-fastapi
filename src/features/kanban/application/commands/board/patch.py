"""Command DTO for Kanban patch operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PatchBoardCommand:
    """Sparse update payload for the patch-board use case.

    Each optional field follows the convention ``None`` means
    "leave unchanged"; the use case rejects empty patches so callers
    cannot accidentally produce no-op writes.
    """

    board_id: str
    title: str | None = None
    actor_id: UUID | None = None

    def has_changes(self) -> bool:
        """Return ``True`` if at least one mutable field carries a value."""
        return self.title is not None
