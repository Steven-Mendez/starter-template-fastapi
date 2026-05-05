from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request

if TYPE_CHECKING:
    from src.features.kanban.composition.container import KanbanContainer

KANBAN_CONTAINER_ATTR = "kanban_container"


def set_kanban_container(app: FastAPI, container: "KanbanContainer") -> None:
    setattr(app.state, KANBAN_CONTAINER_ATTR, container)


def get_kanban_container(request: Request) -> "KanbanContainer":
    container = getattr(request.app.state, KANBAN_CONTAINER_ATTR, None)
    if container is None:
        raise RuntimeError("Kanban container is not initialized in lifespan")
    return container  # type: ignore[no-any-return]
