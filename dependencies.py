from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request

from kanban.repository import KanbanRepository, create_repository_for_settings
from settings import AppSettings, get_settings


@dataclass(slots=True)
class AppContainer:
    settings: AppSettings
    repository: KanbanRepository


def build_container(settings: AppSettings) -> AppContainer:
    return AppContainer(
        settings=settings,
        repository=create_repository_for_settings(settings),
    )


def set_app_container(app: FastAPI, container: AppContainer) -> None:
    app.state.container = container


def get_app_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        container = build_container(get_settings())
        request.app.state.container = container
    return container


def get_app_settings(request: Request) -> AppSettings:
    return get_app_container(request).settings


def get_kanban_repository(request: Request) -> KanbanRepository:
    return get_app_container(request).repository
