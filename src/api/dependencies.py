from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Protocol, TypeAlias, cast

from fastapi import Depends, FastAPI, Request

from src.application.commands import KanbanCommandHandlers
from src.application.queries import KanbanQueryHandlers
from src.application.shared.unit_of_work import UnitOfWork
from src.config.settings import AppSettings
from src.domain.kanban.repository import KanbanRepository

UnitOfWorkFactory: TypeAlias = Callable[[], UnitOfWork]


class AppContainer(Protocol):
    @property
    def settings(self) -> AppSettings: ...

    @property
    def repository(self) -> KanbanRepository: ...

    @property
    def query_handlers(self) -> KanbanQueryHandlers: ...

    @property
    def uow_factory(self) -> UnitOfWorkFactory: ...


def set_app_container(app: FastAPI, container: AppContainer) -> None:
    app.state.container = container


def get_app_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("Application container is not initialized in lifespan")
    return cast(AppContainer, container)


def get_app_settings(request: Request) -> AppSettings:
    return get_app_container(request).settings


def get_kanban_repository(request: Request) -> KanbanRepository:
    return get_app_container(request).repository


def get_kanban_command_handlers(request: Request) -> KanbanCommandHandlers:
    container = get_app_container(request)
    return KanbanCommandHandlers(uow=container.uow_factory())


def get_kanban_query_handlers(request: Request) -> KanbanQueryHandlers:
    return get_app_container(request).query_handlers


AppContainerDep: TypeAlias = Annotated[AppContainer, Depends(get_app_container)]
CommandHandlersDep: TypeAlias = Annotated[
    KanbanCommandHandlers,
    Depends(get_kanban_command_handlers),
]
QueryHandlersDep: TypeAlias = Annotated[
    KanbanQueryHandlers,
    Depends(get_kanban_query_handlers),
]
