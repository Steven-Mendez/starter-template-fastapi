from __future__ import annotations

from typing import Annotated, Protocol, TypeAlias, cast

from fastapi import Depends, FastAPI, Request

from src.platform.config.settings import AppSettings


class DependencyContainerNotReadyError(RuntimeError):
    """Raised when API-edge container wiring is unavailable."""


class AppContainer(Protocol):
    """Minimal platform-level container exposed via ``app.state.container``.

    Feature-specific containers (e.g. Kanban) are wired separately by their
    own composition root and accessed via their feature's wiring helpers.
    """

    @property
    def settings(self) -> AppSettings: ...


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


AppSettingsDep: TypeAlias = Annotated[AppSettings, Depends(get_app_settings)]
