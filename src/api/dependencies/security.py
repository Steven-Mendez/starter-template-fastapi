from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Protocol, TypeAlias, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from src.application.ports.clock_port import ClockPort
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared.readiness import ReadinessProbe

UnitOfWorkFactory: TypeAlias = Callable[[], UnitOfWorkPort]


class DependencyContainerNotReadyError(RuntimeError):
    """Raised when API-edge container wiring is unavailable."""


class AppContainer(Protocol):
    @property
    def settings(self) -> Any: ...

    @property
    def query_repository(self) -> KanbanQueryRepositoryPort: ...

    @property
    def uow_factory(self) -> UnitOfWorkFactory: ...

    @property
    def id_gen(self) -> IdGeneratorPort: ...

    @property
    def clock(self) -> ClockPort: ...

    @property
    def readiness_probe(self) -> ReadinessProbe: ...


def set_app_container(app: FastAPI, container: AppContainer) -> None:
    app.state.container = container


def get_app_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise DependencyContainerNotReadyError(
            "Application container is not initialized in lifespan"
        )
    return cast(AppContainer, container)


def get_app_settings(request: Request) -> Any:
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


AppSettingsDep: TypeAlias = Annotated[Any, Depends(get_app_settings)]
WriteApiKeyDep: TypeAlias = Annotated[None, Depends(require_write_api_key)]
