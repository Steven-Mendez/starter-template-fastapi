from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request

from settings import AppSettings, get_settings
from src.application.commands import KanbanCommandHandlers
from src.application.ports.repository import KanbanRepository
from src.application.queries import KanbanQueryHandlers
from src.application.use_cases import KanbanUseCases
from src.infrastructure.config.di.composition import create_repository_for_settings


@dataclass(slots=True)
class AppContainer:
    settings: AppSettings
    repository: KanbanRepository
    command_handlers: KanbanCommandHandlers
    query_handlers: KanbanQueryHandlers
    use_cases: KanbanUseCases


def build_container(settings: AppSettings) -> AppContainer:
    repository = create_repository_for_settings(settings)
    return AppContainer(
        settings=settings,
        repository=repository,
        command_handlers=KanbanCommandHandlers(repository=repository),
        query_handlers=KanbanQueryHandlers(repository=repository),
        use_cases=KanbanUseCases(repository=repository),
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


def get_kanban_use_cases(request: Request) -> KanbanUseCases:
    return get_app_container(request).use_cases


def get_kanban_command_handlers(request: Request) -> KanbanCommandHandlers:
    return get_app_container(request).command_handlers


def get_kanban_query_handlers(request: Request) -> KanbanQueryHandlers:
    return get_app_container(request).query_handlers
