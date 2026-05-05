from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import FastAPI

from src.features.kanban.composition import (
    attach_kanban_container,
    build_kanban_container,
    mount_kanban_routes,
)
from src.platform.api.app_factory import build_fastapi_app
from src.platform.api.dependencies.container import set_app_container
from src.platform.config.settings import AppSettings, get_settings


@dataclass(frozen=True, slots=True)
class _PlatformAppContainer:
    settings: AppSettings


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = build_fastapi_app(app_settings)

    # Routes are mounted eagerly so OpenAPI reflects them and routing works
    # before lifespan startup completes.
    mount_kanban_routes(app)

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI) -> AsyncIterator[None]:
        kanban = build_kanban_container(postgresql_dsn=app_settings.postgresql_dsn)
        set_app_container(lifespan_app, _PlatformAppContainer(settings=app_settings))
        attach_kanban_container(lifespan_app, kanban)
        try:
            yield
        finally:
            kanban.shutdown()
            lifespan_app.state.container = None

    app.router.lifespan_context = lifespan
    return app


app = create_app()
