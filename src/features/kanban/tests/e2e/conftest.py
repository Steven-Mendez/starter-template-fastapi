"""Pytest fixtures that wire a fully composed FastAPI app for Kanban e2e tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException, status
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


@dataclass(frozen=True, slots=True)
class _AuthContainer:
    principal_cache: object


def _require_test_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if authorization != "Bearer test-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _build_app(settings: AppSettings, wiring: FakeKanbanWiring) -> FastAPI:
    app = build_fastapi_app(settings)
    auth_dependencies = [Depends(_require_test_auth)]
    mount_kanban_routes(
        app,
        read_dependencies=auth_dependencies,
        write_dependencies=auth_dependencies,
    )

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(lifespan_app, _Container(settings=settings))
        lifespan_app.state.auth_container = _AuthContainer(principal_cache=object())
        attach_kanban_container(lifespan_app, wiring.container)
        yield
        lifespan_app.state.container = None
        lifespan_app.state.auth_container = None

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
        c.headers.update({"Authorization": "Bearer test-token"})
        yield c


@pytest.fixture
def unauthenticated_client(
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
        c.headers.update({"Authorization": "Bearer test-token"})
        yield c


@pytest.fixture
def client_without_jwt_secret(
    test_settings: AppSettings, wiring: FakeKanbanWiring
) -> Iterator[TestClient]:
    settings = test_settings.model_copy(update={"auth_jwt_secret_key": None})
    app = _build_app(settings, wiring)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_with_unreachable_redis(
    test_settings: AppSettings, wiring: FakeKanbanWiring
) -> Iterator[TestClient]:
    settings = test_settings.model_copy(
        update={"auth_redis_url": "redis://127.0.0.1:1/0"}
    )
    app = _build_app(settings, wiring)
    with TestClient(app) as c:
        yield c
