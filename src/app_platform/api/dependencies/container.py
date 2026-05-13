"""Helpers for storing and retrieving the platform-level container on ``app.state``."""

from __future__ import annotations

from typing import Annotated, Protocol, cast

from fastapi import Depends, FastAPI, Request

from app_platform.config.settings import AppSettings


class DependencyContainerNotReadyError(RuntimeError):
    """Raised when API-edge container wiring is unavailable.

    Surfaces as a 503 response so misconfigured deployments fail loudly
    instead of returning confusing 500s.
    """


class AppContainer(Protocol):
    """Minimal platform-level container exposed via ``app.state.container``.

    Feature-specific containers are wired separately by their own
    composition root and accessed via their feature's wiring helpers.
    """

    @property
    def settings(self) -> AppSettings: ...


def set_app_container(app: FastAPI, container: AppContainer) -> None:
    """Attach the platform container to ``app`` during lifespan startup."""
    app.state.container = container


def get_app_container(request: Request) -> AppContainer:
    """Return the platform container bound to ``app.state``.

    Raises:
        DependencyContainerNotReadyError: If no container has been
            attached yet (typically because lifespan startup did not run).
    """
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise DependencyContainerNotReadyError(
            "Application container is not initialized in lifespan"
        )
    return cast(AppContainer, container)


def get_app_settings(request: Request) -> AppSettings:
    """Shortcut dependency that returns the active :class:`AppSettings` instance."""
    return get_app_container(request).settings


type AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]
