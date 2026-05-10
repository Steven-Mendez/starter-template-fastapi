"""Glue functions that mount Kanban routes and bind the container to ``app.state``."""

from __future__ import annotations

from fastapi import FastAPI

from src.features.kanban.adapters.inbound.http.router import (
    build_kanban_api_router,
    build_kanban_health_router,
)
from src.features.kanban.composition.app_state import set_kanban_container
from src.features.kanban.composition.container import KanbanContainer


def mount_kanban_routes(app: FastAPI) -> None:
    """Mount the Kanban HTTP routers.

    The Kanban resource API is exposed under ``/api`` and the readiness probe
    at ``/health`` (root level). Per-route ``require_authorization`` checks
    handle ReBAC; the router enforces only authentication.
    """
    app.include_router(build_kanban_api_router())
    app.include_router(build_kanban_health_router())


def attach_kanban_container(app: FastAPI, container: KanbanContainer) -> None:
    """Bind a Kanban container to ``app.state`` (called during lifespan startup)."""
    set_kanban_container(app, container)


def register_kanban(app: FastAPI, container: KanbanContainer) -> None:
    """Convenience: mount routes and bind container in one call."""
    mount_kanban_routes(app)
    attach_kanban_container(app, container)
