from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Protocol, TypeAlias, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from src.application.commands import KanbanCommandInputPort
from src.application.queries import KanbanQueryInputPort
from src.config.settings import AppSettings

CommandHandlersFactory: TypeAlias = Callable[[], KanbanCommandInputPort]


class DependencyContainerNotReadyError(RuntimeError):
    """Raised when API-edge container wiring is unavailable."""


class AppContainer(Protocol):
    @property
    def settings(self) -> AppSettings: ...

    @property
    def query_handlers(self) -> KanbanQueryInputPort: ...

    @property
    def command_handlers_factory(self) -> CommandHandlersFactory: ...


def set_app_container(app: FastAPI, container: AppContainer) -> None:
    app.state.container = container


def get_app_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise DependencyContainerNotReadyError(
            "Application container is not initialized in lifespan"
        )
    return cast(AppContainer, container)


def get_app_settings(request: Request) -> AppSettings:
    return get_app_container(request).settings


def require_write_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    configured_key = get_app_settings(request).write_api_key
    if not configured_key:
        return
    if x_api_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


def get_kanban_command_handlers(request: Request) -> KanbanCommandInputPort:
    container = get_app_container(request)
    return container.command_handlers_factory()


def get_kanban_query_handlers(request: Request) -> KanbanQueryInputPort:
    return get_app_container(request).query_handlers


AppSettingsDep: TypeAlias = Annotated[AppSettings, Depends(get_app_settings)]
CommandHandlersDep: TypeAlias = Annotated[
    KanbanCommandInputPort,
    Depends(get_kanban_command_handlers),
]
QueryHandlersDep: TypeAlias = Annotated[
    KanbanQueryInputPort,
    Depends(get_kanban_query_handlers),
]
WriteApiKeyDep: TypeAlias = Annotated[None, Depends(require_write_api_key)]
