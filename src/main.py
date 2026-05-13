"""Application entry point.

Composes the FastAPI app, mounts every feature router, and wires the
per-feature containers inside the lifespan event so resource ownership
matches the process lifetime: routes are visible from boot, but DB
pools and Redis connections only exist while the app is serving.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import redis as redis_lib
from fastapi import FastAPI

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.dependencies.container import set_app_container
from app_platform.config.settings import AppSettings, get_settings
from app_platform.observability import configure_logging
from app_platform.observability.tracing import configure_tracing, instrument_fastapi_app
from features.authentication.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
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
    AuthorizationContainer,
    attach_authorization_container,
    build_authorization_container,
    register_authorization_error_handlers,
)
from features.background_jobs.composition.container import build_jobs_container
from features.background_jobs.composition.settings import JobsSettings
from features.background_jobs.composition.wiring import attach_jobs_container
from features.email.composition.container import build_email_container
from features.email.composition.jobs import register_send_email_handler
from features.email.composition.settings import EmailSettings
from features.email.composition.wiring import attach_email_container
from features.file_storage.composition.container import (
    build_file_storage_container,
)
from features.file_storage.composition.settings import StorageSettings
from features.file_storage.composition.wiring import attach_file_storage_container
from features.outbox.composition.container import build_outbox_container
from features.outbox.composition.settings import OutboxSettings
from features.outbox.composition.wiring import attach_outbox_container
from features.users.composition.container import (
    build_user_registrar_adapter,
    build_users_container,
)
from features.users.composition.wiring import (
    attach_users_container,
    mount_users_routes,
)


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


def _run_authz_bootstrap(
    authorization: AuthorizationContainer, settings: AppSettings
) -> None:
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
        authorization.bootstrap_system_admin.execute(email=email, password=password)


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
    mount_users_routes(app)
    register_authorization_error_handlers(app)
    instrument_fastapi_app(app, app_settings)

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI) -> AsyncIterator[None]:
        # Build a shared engine via the auth repository, then construct the
        # users container around the same engine before wiring authentication.
        # Auth depends on users.UserPort, so the users container must exist
        # first; the engine outlives both because auth.shutdown disposes it.
        repository = SQLModelAuthRepository(
            app_settings.postgresql_dsn,
            create_schema=False,
            pool_size=app_settings.db_pool_size,
            max_overflow=app_settings.db_max_overflow,
            pool_recycle=app_settings.db_pool_recycle_seconds,
            pool_pre_ping=app_settings.db_pool_pre_ping,
        )
        users = build_users_container(engine=repository.engine)
        email = build_email_container(
            EmailSettings.from_app_settings(
                backend=app_settings.email_backend,
                from_address=app_settings.email_from,
                smtp_host=app_settings.email_smtp_host,
                smtp_port=app_settings.email_smtp_port,
                smtp_username=app_settings.email_smtp_username,
                smtp_password=app_settings.email_smtp_password,
                smtp_use_starttls=app_settings.email_smtp_use_starttls,
                smtp_use_ssl=app_settings.email_smtp_use_ssl,
                smtp_timeout_seconds=app_settings.email_smtp_timeout_seconds,
            )
        )
        register_authentication_email_templates(email.registry)
        # Every feature that contributes templates has now done so.
        email.registry.seal()
        # Build the jobs container after email so the email feature's
        # send_email handler can register itself with the queue's registry.
        # The arq adapter, when selected, reuses the shared rate-limit/cache
        # Redis URL if APP_JOBS_REDIS_URL is unset.
        jobs = build_jobs_container(
            JobsSettings.from_app_settings(
                backend=app_settings.jobs_backend,
                redis_url=app_settings.jobs_redis_url or app_settings.auth_redis_url,
                queue_name=app_settings.jobs_queue_name,
            )
        )
        register_send_email_handler(jobs.registry, email.port)
        jobs.registry.seal()
        # Outbox sits between jobs and auth: it depends on the engine and
        # the JobQueuePort, and authentication's request-path consumers
        # consume the outbox unit-of-work port so their writes commit
        # atomically with the outbox row.
        outbox = build_outbox_container(
            OutboxSettings.from_app_settings(app_settings),
            engine=repository.engine,
            job_queue=jobs.port,
        )
        auth = build_auth_container(
            settings=app_settings,
            users=users.user_repository,
            outbox_uow=outbox.unit_of_work,
            repository=repository,
        )
        user_registrar = build_user_registrar_adapter(
            users=users,
            credential_writer=auth.credential_writer_adapter,
        )
        authorization = build_authorization_container(
            engine=repository.engine,
            user_authz_version=users.user_authz_version_adapter,
            user_registrar=user_registrar,
            audit=auth.audit_adapter,
        )
        file_storage = build_file_storage_container(
            StorageSettings.from_app_settings(app_settings)
        )
        # Every feature has now contributed to the registry; freeze it
        # so a stray runtime ``register_…`` call surfaces as a clear error
        # rather than a silent behaviour change.
        authorization.registry.seal()
        _run_authz_bootstrap(authorization, app_settings)
        set_app_container(lifespan_app, _PlatformAppContainer(settings=app_settings))
        # Register the principal resolver so platform-level authorization
        # dependencies (require_authorization, etc.) can resolve tokens
        # without importing from the auth feature.
        lifespan_app.state.principal_resolver = auth.resolve_principal.execute
        attach_authorization_container(lifespan_app, authorization)
        attach_auth_container(lifespan_app, auth)
        attach_users_container(lifespan_app, users)
        attach_email_container(lifespan_app, email)
        attach_jobs_container(lifespan_app, jobs)
        attach_outbox_container(lifespan_app, outbox)
        attach_file_storage_container(lifespan_app, file_storage)

        # Shared Redis client used by health probes and other platform consumers.
        # Stored on app.state so it can be injected without coupling features.
        redis_client: redis_lib.Redis | None = None
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
            outbox.shutdown()
            jobs.shutdown()
            users.shutdown()
            authorization.shutdown()
            auth.shutdown()
            if redis_client is not None:
                redis_client.close()
            lifespan_app.state.container = None
            lifespan_app.state.redis_client = None

    app.router.lifespan_context = lifespan
    return app


app = create_app()
