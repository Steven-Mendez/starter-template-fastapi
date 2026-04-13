"""Compatibility exports for the Kanban persistence layer (repository pattern)."""

from __future__ import annotations

from kanban.repository import (
    DUE_AT_UNSET as REPOSITORY_DUE_AT_UNSET,
    InMemoryKanbanRepository,
    KanbanRepository,
    get_repository,
)

KanbanStore = InMemoryKanbanRepository
DUE_AT_UNSET = REPOSITORY_DUE_AT_UNSET


def get_store() -> KanbanRepository:
    return get_repository()
