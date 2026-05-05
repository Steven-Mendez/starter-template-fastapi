from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.features.kanban.composition import (
    attach_kanban_container,
    mount_kanban_routes,
)
from src.features.kanban.tests.fakes import (
    FakeKanbanWiring,
    InMemoryKanbanRepository,
    build_fake_kanban_wiring,
)
from src.platform.api.app_factory import build_fastapi_app
from src.platform.api.dependencies.container import set_app_container
from src.platform.config.settings import AppSettings


@dataclass(frozen=True, slots=True)
class _Container:
    settings: AppSettings


def _build_app(settings: AppSettings, wiring: FakeKanbanWiring) -> FastAPI:
    app = build_fastapi_app(settings)
    mount_kanban_routes(app)

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(lifespan_app, _Container(settings=settings))
        attach_kanban_container(lifespan_app, wiring.container)
        yield
        lifespan_app.state.container = None

    app.router.lifespan_context = lifespan
    return app


@pytest.fixture
def repository() -> InMemoryKanbanRepository:
    return InMemoryKanbanRepository()


@pytest.fixture
def wiring(repository: InMemoryKanbanRepository) -> FakeKanbanWiring:
    return build_fake_kanban_wiring(repository=repository)


@pytest.fixture
def client(
    test_settings: AppSettings, wiring: FakeKanbanWiring
) -> Iterator[TestClient]:
    app = _build_app(test_settings, wiring)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def secured_settings(test_settings: AppSettings) -> AppSettings:
    return test_settings.model_copy(update={"write_api_key": "secret"})


@pytest.fixture
def secured_client(
    secured_settings: AppSettings, wiring: FakeKanbanWiring
) -> Iterator[TestClient]:
    app = _build_app(secured_settings, wiring)
    with TestClient(app) as c:
        yield c
