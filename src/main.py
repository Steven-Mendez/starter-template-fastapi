"""Application entry point.

Composes the FastAPI app, mounts every feature router, and wires the
per-feature containers inside the lifespan event so resource ownership
matches the process lifetime: routes are visible from boot, but DB
pools and Redis connections only exist while the app is serving.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import redis as redis_lib
from fastapi import FastAPI

from src.features.auth.composition.container import AuthContainer, build_auth_container
from src.features.auth.composition.wiring import (
    attach_auth_container,
    mount_auth_routes,
)
from src.features.kanban.composition import (
    attach_kanban_container,
    build_kanban_container,
    mount_kanban_routes,
)
from src.platform.api.app_factory import build_fastapi_app
from src.platform.api.dependencies.container import set_app_container
from src.platform.config.settings import AppSettings, get_settings
from src.platform.observability import configure_logging
from src.platform.observability.tracing import configure_tracing, instrument_fastapi_app


@dataclass(frozen=True, slots=True)
class _PlatformAppContainer:
    """Thin wrapper on ``app.state`` exposing settings to platform code."""

    settings: AppSettings


def _configure_logging(settings: AppSettings) -> None:
    """Configure root logging with JSON output outside of development."""
    configure_logging(
        level=settings.log_level,
        json_format=settings.environment != "development",
        service_name=settings.otel_service_name,
        service_version=settings.otel_service_version,
        environment=settings.environment,
    )


def _run_auth_bootstrap(auth: AuthContainer, settings: AppSettings) -> None:
    """Optionally create the first ``system:main#admin`` tuple at startup.

    Idempotent: re-runs against an already-bootstrapped DB simply re-write
    the same relationship tuple (no-op via the unique constraint).
    """
    if not settings.auth_seed_on_startup:
        return

    email = settings.auth_bootstrap_super_admin_email
    password = settings.auth_bootstrap_super_admin_password
    if bool(email) != bool(password):
        raise RuntimeError(
            "APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL and "
            "APP_AUTH_BOOTSTRAP_SUPER_ADMIN_PASSWORD must be set together."
        )
    if email and password:
        auth.bootstrap_system_admin.execute(email=email, password=password)


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Build the FastAPI application and configure its lifespan."""
    app_settings = settings or get_settings()
    _configure_logging(app_settings)
    configure_tracing(app_settings)
    app = build_fastapi_app(app_settings)

    # Routes are mounted eagerly so OpenAPI reflects them and routing works
    # before lifespan startup completes. Containers are attached in lifespan
    # because they require DB connections that should not outlive the process.
    mount_auth_routes(app)
    mount_kanban_routes(app)
    instrument_fastapi_app(app, app_settings)

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI) -> AsyncIterator[None]:
        auth = build_auth_container(settings=app_settings)
        kanban = build_kanban_container(
            postgresql_dsn=app_settings.postgresql_dsn,
            authorization=auth.authorization,
            registry=auth.registry,
            pool_size=app_settings.db_pool_size,
            max_overflow=app_settings.db_max_overflow,
            pool_recycle=app_settings.db_pool_recycle_seconds,
            pool_pre_ping=app_settings.db_pool_pre_ping,
        )
        # Every feature has now contributed to the registry; freeze it
        # so a stray runtime ``register_…`` call surfaces as a clear error
        # rather than a silent behaviour change.
        auth.registry.seal()
        _run_auth_bootstrap(auth, app_settings)
        set_app_container(lifespan_app, _PlatformAppContainer(settings=app_settings))
        # Register the principal resolver so platform-level authorization
        # dependencies (require_authorization, etc.) can resolve tokens
        # without importing from the auth feature.
        lifespan_app.state.principal_resolver = auth.resolve_principal.execute
        attach_auth_container(lifespan_app, auth)
        attach_kanban_container(lifespan_app, kanban)

        # Shared Redis client used by health probes and other platform consumers.
        # Stored on app.state so it can be injected without coupling features.
        redis_client: redis_lib.Redis | None = None  # type: ignore[type-arg]
        if app_settings.auth_redis_url:
            # Bound socket waits so a slow or unreachable Redis cannot stall
            # health probes or rate-limit checks indefinitely. Liveness will
            # fail fast and report ``redis.ready=false`` instead.
            redis_client = redis_lib.Redis.from_url(
                app_settings.auth_redis_url,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
        lifespan_app.state.redis_client = redis_client

        try:
            yield
        finally:
            # Shutdown order is reverse of startup so dependent resources
            # (e.g. connection pools) are closed after the services that use them.
            kanban.shutdown()
            auth.shutdown()
            if redis_client is not None:
                redis_client.close()
            lifespan_app.state.container = None
            lifespan_app.state.redis_client = None

    app.router.lifespan_context = lifespan
    return app


app = create_app()
