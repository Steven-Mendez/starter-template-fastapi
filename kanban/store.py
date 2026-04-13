"""Compatibility exports for the Kanban persistence layer (repository pattern)."""

from __future__ import annotations

from fastapi import Request

from dependencies import get_kanban_repository
from kanban import repository

KanbanStore = repository.InMemoryKanbanRepository
DUE_AT_UNSET = repository.DUE_AT_UNSET


def get_store(request: Request) -> repository.KanbanRepository:
    return get_kanban_repository(request)
