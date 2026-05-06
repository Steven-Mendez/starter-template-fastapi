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
    at ``/health`` (root level) for compatibility with platform health probes.
    Call at app build time (before lifespan) so routes are visible immediately
    for OpenAPI generation and request routing.
    """
    app.include_router(build_kanban_api_router())
    app.include_router(build_kanban_health_router())


def attach_kanban_container(app: FastAPI, container: KanbanContainer) -> None:
    """Bind a Kanban container to ``app.state`` (called during lifespan startup)."""
    set_kanban_container(app, container)


def register_kanban(app: FastAPI, container: KanbanContainer) -> None:
    """Convenience: mount routes and bind container in one call.

    Prefer calling :func:`mount_kanban_routes` at app build time and
    :func:`attach_kanban_container` from lifespan startup.
    """
    mount_kanban_routes(app)
    attach_kanban_container(app, container)
