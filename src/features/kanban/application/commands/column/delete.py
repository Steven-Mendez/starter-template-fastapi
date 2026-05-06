"""Command DTO for Kanban delete operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeleteColumnCommand:
    column_id: str
