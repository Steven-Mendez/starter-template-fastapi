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
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.dependencies.container import set_app_container
from app_platform.config.settings import AppSettings
from app_platform.persistence.sqlmodel.authorization.models import RelationshipTable
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    CredentialTable,
    RefreshTokenTable,
)
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authentication.adapters.outbound.principal_cache_invalidator import (
    PrincipalCacheInvalidatorAdapter,
)
from features.authentication.composition.container import build_auth_container
from features.authentication.composition.wiring import (
    attach_auth_container,
    mount_auth_routes,
)
from features.authentication.email_templates import (
    register_authentication_email_templates,
)
from features.authorization.composition import (
    attach_authorization_container,
    build_authorization_container,
    register_authorization_error_handlers,
)
from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.registry import JobHandlerRegistry
from features.email.composition.container import build_email_container
from features.email.composition.jobs import register_send_email_handler
from features.email.composition.settings import EmailSettings
from features.email.composition.wiring import attach_email_container
from features.email.tests.fakes.fake_email_port import FakeEmailPort
from features.outbox.tests.fakes.fake_outbox import InlineDispatchOutboxUnitOfWork
from features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
)
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from features.users.composition.container import (
    build_user_registrar_adapter,
    build_users_container,
)
from features.users.composition.wiring import (
    attach_users_container,
    mount_users_routes,
)


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
    user_repository: SQLModelUserRepository
    email: FakeEmailPort


AUTH_TABLES: list[Any] = [
    UserTable,
    RelationshipTable,
    CredentialTable,
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


def _build_app(
    settings: AppSettings,
    repository: SQLModelAuthRepository,
    email_port: FakeEmailPort,
) -> tuple[FastAPI, SQLModelUserRepository]:
    """Build a wired FastAPI app with a bootstrapped system-admin account."""
    app = build_fastapi_app(settings)
    mount_auth_routes(app)
    mount_users_routes(app)
    register_authorization_error_handlers(app)
    users = build_users_container(engine=repository.engine)
    email_container = build_email_container(
        EmailSettings.from_app_settings(
            backend="console",
            from_address="test@example.com",
            smtp_host=None,
            smtp_port=587,
            smtp_username=None,
            smtp_password=None,
            smtp_use_starttls=False,
            smtp_use_ssl=False,
            smtp_timeout_seconds=1.0,
        )
    )
    register_authentication_email_templates(email_container.registry)
    email_container.registry.seal()
    # Auth's password-reset/email-verify flows enqueue ``send_email``
    # via the jobs port. Wiring the in-process queue with the
    # ``send_email`` handler bound to the fake email port keeps the
    # e2e tests able to inspect ``email_port.sent`` for behavioural
    # assertions exactly as before.
    jobs_registry = JobHandlerRegistry()
    register_send_email_handler(jobs_registry, email_port)
    jobs_registry.seal()
    jobs_port = InProcessJobQueueAdapter(registry=jobs_registry)

    # In e2e tests we dispatch outbox rows inline at enqueue time — the
    # SQLite test engine cannot run the real ``FOR UPDATE SKIP LOCKED``
    # relay (Postgres-only). Atomicity guarantees are exercised by
    # ``tests/integration/test_password_reset_atomicity.py`` against a
    # real Postgres via testcontainers.
    outbox_uow = InlineDispatchOutboxUnitOfWork(dispatcher=jobs_port.enqueue)

    auth = build_auth_container(
        settings=settings,
        users=users.user_repository,
        outbox_uow=outbox_uow,
        repository=repository,
    )

    def _revoke_all_refresh_tokens(user_id: UUID) -> None:
        auth.logout_all_sessions.execute(user_id=user_id)

    users.wire_refresh_token_revoker(_revoke_all_refresh_tokens)
    user_registrar = build_user_registrar_adapter(
        users=users, credential_writer=auth.credential_writer_adapter
    )
    authorization = build_authorization_container(
        engine=repository.engine,
        user_authz_version=users.user_authz_version_adapter,
        user_registrar=user_registrar,
        audit=auth.audit_adapter,
        principal_cache_invalidator=PrincipalCacheInvalidatorAdapter(
            auth.principal_cache
        ),
    )
    authorization.registry.seal()
    authorization.bootstrap_system_admin.execute(
        email="admin@example.com",
        password="AdminPassword123!",
    )

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(lifespan_app, _Container(settings=settings))
        # Register the principal resolver so platform-level dependencies
        # (require_authorization) can resolve tokens via app.state.
        lifespan_app.state.principal_resolver = auth.resolve_principal.execute
        attach_authorization_container(lifespan_app, authorization)
        attach_auth_container(lifespan_app, auth)
        attach_users_container(lifespan_app, users)
        attach_email_container(lifespan_app, email_container)
        yield
        lifespan_app.state.container = None

    app.router.lifespan_context = lifespan
    return app, users.user_repository


@pytest.fixture
def auth_context(
    test_settings: AppSettings,
    auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthTestContext]:
    """Yield a fully composed :class:`AuthTestContext` for an e2e test."""
    settings = _settings(test_settings)
    email_port = FakeEmailPort()
    app, user_repository = _build_app(settings, auth_repository, email_port)
    with TestClient(app) as client:
        yield AuthTestContext(
            client=client,
            repository=auth_repository,
            user_repository=user_repository,
            email=email_port,
        )


@pytest.fixture
def auth_context_rate_limited(
    test_settings: AppSettings,
    auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthTestContext]:
    """Same as ``auth_context`` with ``auth_rate_limit_enabled`` set to True."""
    settings = _settings(test_settings).model_copy(
        update={"auth_rate_limit_enabled": True}
    )
    email_port = FakeEmailPort()
    app, user_repository = _build_app(settings, auth_repository, email_port)
    with TestClient(app) as client:
        yield AuthTestContext(
            client=client,
            repository=auth_repository,
            user_repository=user_repository,
            email=email_port,
        )


@pytest.fixture
def auth_context_internal_tokens_hidden(
    test_settings: AppSettings,
    auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthTestContext]:
    """Same as ``auth_context`` but internal one-time tokens are not returned."""
    settings = _settings(test_settings).model_copy(
        update={"auth_return_internal_tokens": False}
    )
    email_port = FakeEmailPort()
    app, user_repository = _build_app(settings, auth_repository, email_port)
    with TestClient(app) as client:
        yield AuthTestContext(
            client=client,
            repository=auth_repository,
            user_repository=user_repository,
            email=email_port,
        )


@pytest.fixture
def auth_context_email_verification_required(
    test_settings: AppSettings,
    auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthTestContext]:
    """Same as ``auth_context`` but login requires verified email addresses."""
    settings = _settings(test_settings).model_copy(
        update={"auth_require_email_verification": True}
    )
    email_port = FakeEmailPort()
    app, user_repository = _build_app(settings, auth_repository, email_port)
    with TestClient(app) as client:
        yield AuthTestContext(
            client=client,
            repository=auth_repository,
            user_repository=user_repository,
            email=email_port,
        )


@pytest.fixture
def client(auth_context: AuthTestContext) -> TestClient:
    """Shortcut fixture for tests that only need the HTTP client."""
    return auth_context.client
