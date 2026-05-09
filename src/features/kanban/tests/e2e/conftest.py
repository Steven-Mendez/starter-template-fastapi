"""Pytest fixtures that wire a fully composed FastAPI app for Kanban e2e tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

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
from src.platform.api.authorization import require_permissions
from src.platform.api.dependencies.container import set_app_container
from src.platform.config.settings import AppSettings
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok


@dataclass(frozen=True, slots=True)
class _Container:
    settings: AppSettings


@dataclass(frozen=True, slots=True)
class _AuthContainer:
    principal_cache: object


_AUTHED_PRINCIPAL = Principal(
    user_id=uuid4(),
    email="test@example.com",
    is_active=True,
    is_verified=True,
    authz_version=1,
    roles=frozenset({"user"}),
    permissions=frozenset({"kanban:read", "kanban:write"}),
)

_READ_ONLY_PRINCIPAL = Principal(
    user_id=uuid4(),
    email="readonly@example.com",
    is_active=True,
    is_verified=True,
    authz_version=1,
    roles=frozenset({"manager"}),
    permissions=frozenset({"kanban:read"}),
)


class _InvalidTokenError(Exception):
    pass


def _fake_resolver(token: str) -> object:
    if token == "test-token":
        return Ok(_AUTHED_PRINCIPAL)
    if token == "read-only-token":
        return Ok(_READ_ONLY_PRINCIPAL)
    return Err(_InvalidTokenError("invalid token"))


def _build_app(settings: AppSettings, wiring: FakeKanbanWiring) -> FastAPI:
    app = build_fastapi_app(settings)
    read_guard = [require_permissions("kanban:read")]
    write_guard = [require_permissions("kanban:write")]
    mount_kanban_routes(
        app,
        read_dependencies=read_guard,
        write_dependencies=write_guard,
    )

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(lifespan_app, _Container(settings=settings))
        lifespan_app.state.principal_resolver = _fake_resolver
        lifespan_app.state.auth_container = _AuthContainer(principal_cache=object())
        attach_kanban_container(lifespan_app, wiring.container)
        yield
        lifespan_app.state.container = None
        lifespan_app.state.principal_resolver = None
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
def read_only_client(
    test_settings: AppSettings, wiring: FakeKanbanWiring
) -> Iterator[TestClient]:
    """Client authenticated with kanban:read but not kanban:write."""
    app = _build_app(test_settings, wiring)
    with TestClient(app) as c:
        c.headers.update({"Authorization": "Bearer read-only-token"})
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
