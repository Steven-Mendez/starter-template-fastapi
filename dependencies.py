from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request

from settings import AppSettings, get_settings
from src.application.commands import KanbanCommandHandlers
from src.domain.kanban.repository import KanbanRepository
from src.application.queries import KanbanQueryHandlers
from src.application.shared.unit_of_work import UnitOfWork
from src.infrastructure.config.di.composition import create_repository_for_settings


@dataclass(slots=True)
class AppContainer:
    settings: AppSettings
    repository: KanbanRepository
    query_handlers: KanbanQueryHandlers


def build_container(settings: AppSettings) -> AppContainer:
    repository = create_repository_for_settings(settings)
    return AppContainer(
        settings=settings,
        repository=repository,
        query_handlers=KanbanQueryHandlers(repository=repository),
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


def get_kanban_uow(request: Request) -> UnitOfWork:
    repo = get_kanban_repository(request)
    if hasattr(repo, "_engine"):
        from src.infrastructure.persistence.sqlmodel_uow import SqlModelUnitOfWork
        return SqlModelUnitOfWork(getattr(repo, "_engine"))
    else:
        from src.infrastructure.persistence.in_memory_uow import InMemoryUnitOfWork
        from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository
        import typing
        return InMemoryUnitOfWork(typing.cast(InMemoryKanbanRepository, repo))


def get_kanban_command_handlers(request: Request) -> KanbanCommandHandlers:
    return KanbanCommandHandlers(uow=get_kanban_uow(request))


def get_kanban_query_handlers(request: Request) -> KanbanQueryHandlers:
    return get_app_container(request).query_handlers
