"""Helpers for storing and retrieving the Kanban container on ``app.state``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request

if TYPE_CHECKING:
    from src.features.kanban.composition.container import KanbanContainer

KANBAN_CONTAINER_ATTR = "kanban_container"


def set_kanban_container(app: FastAPI, container: "KanbanContainer") -> None:
    """Attach a Kanban container to the FastAPI app, called during lifespan startup."""
    setattr(app.state, KANBAN_CONTAINER_ATTR, container)


def get_kanban_container(request: Request) -> "KanbanContainer":
    """Return the Kanban container bound to ``app.state``.

    Raises:
        RuntimeError: If no container has been attached yet, which
            usually means the lifespan event did not run (e.g. test
            wiring is missing :func:`attach_kanban_container`).
    """
    container = getattr(request.app.state, KANBAN_CONTAINER_ATTR, None)
    if container is None:
        raise RuntimeError("Kanban container is not initialized in lifespan")
    return container  # type: ignore[no-any-return]
