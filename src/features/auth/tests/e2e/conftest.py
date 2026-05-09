"""Pytest fixtures that bootstrap a fully wired FastAPI app for auth e2e tests.

The fixtures use a SQLite in-memory database with a static connection pool
so every test runs against an isolated, transient schema while still
exercising the real SQLModel mappings, the real composition root, and the
real HTTP layer through ``TestClient``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    PermissionTable,
    RefreshTokenTable,
    RolePermissionTable,
    RoleTable,
    UserRoleTable,
    UserTable,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.auth.composition.container import build_auth_container
from src.features.auth.composition.wiring import (
    attach_auth_container,
    mount_auth_routes,
)
from src.platform.api.app_factory import build_fastapi_app
from src.platform.api.dependencies.container import set_app_container
from src.platform.config.settings import AppSettings


@dataclass(frozen=True, slots=True)
class _Container:
    """Minimal platform-container stand-in with only settings tests need."""

    settings: AppSettings


@dataclass(slots=True)
class AuthTestContext:
    """Bundle of test helpers handed to e2e tests.

    Exposes the HTTP ``TestClient`` for driving requests and the
    ``SQLModelAuthRepository`` so individual tests can assert side
    effects in the database (e.g. inspecting audit events) without
    going through the public API.
    """

    client: TestClient
    repository: SQLModelAuthRepository


AUTH_TABLES: list[Any] = [
    UserTable,
    RoleTable,
    PermissionTable,
    UserRoleTable,
    RolePermissionTable,
    RefreshTokenTable,
    AuthAuditEventTable,
    AuthInternalTokenTable,
]


def _settings(settings: AppSettings) -> AppSettings:
    """Return a copy of ``settings`` tuned for deterministic e2e behaviour.

    Internal tokens are returned in responses, rate limiting is disabled,
    and cookies are not marked secure so the test client can read them
    over the in-memory transport.
    """
    return settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_rate_limit_enabled": False,
            "auth_cookie_secure": False,
            # Force in-memory limiter so tests don't require a running Redis.
            "auth_redis_url": None,
        }
    )


@pytest.fixture
def auth_repository() -> Iterator[SQLModelAuthRepository]:
    """Provide a SQLite in-memory repository with the auth schema pre-created.

    Using ``StaticPool`` keeps a single connection alive across the test
    so the in-memory database is not destroyed between operations.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in AUTH_TABLES:
        table.__table__.create(engine, checkfirst=True)
    repository = SQLModelAuthRepository.from_engine(engine)
    try:
        yield repository
    finally:
        repository.close()


def _build_app(settings: AppSettings, repository: SQLModelAuthRepository) -> FastAPI:
    """Build a wired FastAPI app with seeded RBAC and a super-admin account."""
    app = build_fastapi_app(settings)
    mount_auth_routes(app)
    auth = build_auth_container(settings=settings, repository=repository)
    auth.rbac_service.seed_initial_data()
    auth.rbac_service.bootstrap_super_admin(
        auth_service=auth.auth_service,
        email="admin@example.com",
        password="AdminPassword123!",
    )

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(lifespan_app, _Container(settings=settings))
        attach_auth_container(lifespan_app, auth)
        yield
        lifespan_app.state.container = None

    app.router.lifespan_context = lifespan
    return app


@pytest.fixture
def auth_context(
    test_settings: AppSettings,
    auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthTestContext]:
    """Yield a fully composed :class:`AuthTestContext` for an e2e test."""
    settings = _settings(test_settings)
    app = _build_app(settings, auth_repository)
    with TestClient(app) as client:
        yield AuthTestContext(client=client, repository=auth_repository)


@pytest.fixture
def auth_context_rate_limited(
    test_settings: AppSettings,
    auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthTestContext]:
    """Same as ``auth_context`` with ``auth_rate_limit_enabled`` set to True."""
    settings = _settings(test_settings).model_copy(
        update={"auth_rate_limit_enabled": True}
    )
    app = _build_app(settings, auth_repository)
    with TestClient(app) as client:
        yield AuthTestContext(client=client, repository=auth_repository)


@pytest.fixture
def auth_context_internal_tokens_hidden(
    test_settings: AppSettings,
    auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthTestContext]:
    """Same as ``auth_context`` but internal one-time tokens are not returned."""
    settings = _settings(test_settings).model_copy(
        update={"auth_return_internal_tokens": False}
    )
    app = _build_app(settings, auth_repository)
    with TestClient(app) as client:
        yield AuthTestContext(client=client, repository=auth_repository)


@pytest.fixture
def auth_context_email_verification_required(
    test_settings: AppSettings,
    auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthTestContext]:
    """Same as ``auth_context`` but login requires verified email addresses."""
    settings = _settings(test_settings).model_copy(
        update={"auth_require_email_verification": True}
    )
    app = _build_app(settings, auth_repository)
    with TestClient(app) as client:
        yield AuthTestContext(client=client, repository=auth_repository)


@pytest.fixture
def client(auth_context: AuthTestContext) -> TestClient:
    """Shortcut fixture for tests that only need the HTTP client."""
    return auth_context.client
