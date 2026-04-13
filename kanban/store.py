"""Compatibility exports for the Kanban persistence layer (repository pattern)."""

from __future__ import annotations

from fastapi import Request

from kanban import repository

KanbanStore = repository.InMemoryKanbanRepository
DUE_AT_UNSET = repository.DUE_AT_UNSET


def get_store(request: Request) -> repository.KanbanRepository:
    app_repo = getattr(request.app.state, "repository", None)
    if app_repo is not None:
        return app_repo
    return repository.get_repository()
