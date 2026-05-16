"""Application entry point.

Composes the FastAPI app, mounts every feature router, and wires the
per-feature containers inside the lifespan event so resource ownership
matches the process lifetime: routes are visible from boot, but DB
pools and Redis connections only exist while the app is serving.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

try:  # pragma: no cover - import-time only
    import redis as redis_lib
except ModuleNotFoundError:  # pragma: no cover - exercised in api-only images
    redis_lib = None  # type: ignore[assignment]
from fastapi import FastAPI

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.dependencies.container import set_app_container
from app_platform.api.lifespan import safe_finalize
from app_platform.config.settings import AppSettings, get_settings
from app_platform.observability import configure_logging
from app_platform.observability.metrics import (
    register_db_pool_gauges,
    register_outbox_pending_callback,
)
from app_platform.observability.redaction import redact_email
from app_platform.observability.tracing import (
    configure_tracing,
    instrument_fastapi_app,
    shutdown_tracing,
)
from app_platform.shared.result import Err, Ok
from features.authentication.adapters.outbound.auth_artifacts_cleanup import (
    SQLModelAuthArtifactsCleanupAdapter,
)
from features.authentication.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
)
from features.authentication.adapters.outbound.principal_cache_invalidator import (
    PrincipalCacheInvalidatorAdapter,
)
from features.authentication.adapters.outbound.user_audit_reader import (
    SQLModelUserAuditReaderAdapter,
)
from features.authentication.composition.container import build_auth_container
from features.authentication.composition.wiring import (
    attach_auth_container,
    mount_auth_routes,
)
from features.authentication.email_templates import (
    register_authentication_email_templates,
)
from features.authorization.application.errors import (
    BootstrapPasswordMismatchError,
    BootstrapRefusedExistingUserError,
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
from features.outbox.composition.handler_dedupe import build_handler_dedupe
from features.outbox.composition.settings import OutboxSettings
from features.outbox.composition.wiring import attach_outbox_container
from features.users.composition.container import (
    build_user_registrar_adapter,
    build_users_container,
)
from features.users.composition.jobs import (
    register_delete_user_assets_handler,
    register_erase_user_handler,
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


_bootstrap_logger = logging.getLogger("app.bootstrap")


def _run_authz_bootstrap(
    authorization: AuthorizationContainer, settings: AppSettings
) -> None:
    """Optionally create the first ``system:main#admin`` tuple at startup.

    Idempotent: re-runs against an already-bootstrapped DB return
    ``Ok`` without writing. Refuses with ``SystemExit(2)`` when the
    configured email collides with a pre-existing non-admin account
    unless the operator has opted in via
    ``APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`` AND supplied the
    correct password — the default-deny posture is what closes the
    ``fix-bootstrap-admin-escalation`` privilege-escalation hole.
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
    if not (email and password):
        return

    result = authorization.bootstrap_system_admin.execute(
        email=email, password=password
    )
    match result:
        case Ok():
            return
        case Err(error=BootstrapRefusedExistingUserError() as err):
            # ``err.email`` is masked at the call site because positional
            # %s args bypass the stdlib PII filter (it scans record
            # attributes, not string args).
            _bootstrap_logger.error(
                "event=auth.bootstrap.refused_existing user_id=%s email=%s "
                "message=Refusing to promote existing non-admin user to "
                "system admin. Set APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true "
                "and re-supply the user's actual password to opt in.",
                err.user_id,
                redact_email(err.email),
            )
            raise SystemExit(2)
        case Err(error=BootstrapPasswordMismatchError() as err):
            _bootstrap_logger.error(
                "event=auth.bootstrap.password_mismatch user_id=%s "
                "message=Bootstrap password did not match the existing "
                "user's credential — refusing to promote.",
                err.user_id,
            )
            raise SystemExit(2)


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
        # Bind observable-metric callbacks now that the engine exists.
        # The pool gauges read in-memory pool counters per scrape; the
        # outbox pending gauge runs a bounded COUNT(*) against the same
        # engine. Both helpers are idempotent at the SDK level.
        register_db_pool_gauges(repository.engine)
        register_outbox_pending_callback(repository.engine)
        email = build_email_container(
            EmailSettings.from_app_settings(
                backend=app_settings.email_backend,
                from_address=app_settings.email_from,
                console_log_bodies=app_settings.email_console_log_bodies,
            ),
            environment=app_settings.environment,
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
        # Outbox sits between jobs and auth: it depends on the engine and
        # the JobQueuePort, and authentication's request-path consumers
        # consume the outbox unit-of-work port so their writes commit
        # atomically with the outbox row.
        outbox = build_outbox_container(
            OutboxSettings.from_app_settings(app_settings),
            engine=repository.engine,
            job_queue=jobs.port,
        )
        # File storage is built before users because the users container
        # takes ``FileStoragePort`` as a dependency for its per-user
        # asset-cleanup adapter; the cleanup handler runs out-of-band
        # in the worker after ``DeactivateUser`` / ``EraseUser`` enqueue
        # the ``delete_user_assets`` job through the outbox.
        file_storage = build_file_storage_container(
            StorageSettings.from_app_settings(app_settings)
        )
        users = build_users_container(
            engine=repository.engine,
            file_storage=file_storage.port,
            outbox_uow=outbox.unit_of_work,
        )
        # Register send_email with a dedupe callable backed by the outbox
        # feature's ``processed_outbox_messages`` table; safe even though
        # the web process never runs the relay — the in-process queue used
        # in dev/test still reaches the handler.
        register_send_email_handler(
            jobs.registry,
            email.port,
            dedupe=build_handler_dedupe(repository.engine),
        )
        # Register the ``delete_user_assets`` handler on the same
        # registry. Web and worker processes both register against the
        # same name so producers can never enqueue a payload the
        # consumer side will not recognise.
        register_delete_user_assets_handler(
            jobs.registry,
            users.user_assets_cleanup,
            dedupe=build_handler_dedupe(repository.engine),
        )
        # ``erase_user`` is registered after we wire the use case below,
        # so the handler closes over a fully-constructed ``EraseUser``.
        # Sealing is similarly deferred to after that wiring.
        auth = build_auth_container(
            settings=app_settings,
            users=users.user_repository,
            outbox_uow=outbox.unit_of_work,
            user_writer_factory=users.session_user_writer_factory(),
            repository=repository,
        )

        # Wire the auth-side refresh-token revoker into the users feature so
        # ``DELETE /me`` revokes server-side refresh-token families inside
        # the same Unit of Work as the ``is_active=False`` flip. The
        # collaborator is a plain callable to keep ``users`` from importing
        # the authentication use-case type.
        def _revoke_all_refresh_tokens(user_id: UUID) -> None:
            auth.logout_all_sessions.execute(user_id=user_id)

        users.wire_refresh_token_revoker(_revoke_all_refresh_tokens)
        # Wire the GDPR Art. 17 / Art. 15 use cases now that the auth
        # container exists. The artifacts-cleanup adapter scrubs
        # authentication-owned PII inside the erasure transaction; the
        # audit-reader adapter feeds the export blob. Both are
        # constructed here because they reach into the auth schema and
        # cannot live in the users container's default wiring.
        users.wire_erase_user(
            auth_artifacts=SQLModelAuthArtifactsCleanupAdapter(
                engine=repository.engine
            ),
            audit_reader=SQLModelUserAuditReaderAdapter(repository=repository),
            outbox_uow=outbox.unit_of_work,
            file_storage=file_storage.port,
        )
        users.wire_password_verifier(auth.verify_user_password)
        users.wire_job_queue(jobs.port)
        # Now that ``EraseUser`` is wired, register its job handler and
        # seal the jobs registry so producers cannot enqueue unknown
        # payloads.
        if users.erase_user is None:
            raise RuntimeError("EraseUser was not wired into the users container")
        register_erase_user_handler(
            jobs.registry,
            users.erase_user,
            dedupe=build_handler_dedupe(repository.engine),
        )
        jobs.registry.seal()
        user_registrar = build_user_registrar_adapter(
            users=users,
            credential_writer=auth.credential_writer_adapter,
        )
        # Build the auth-side cache-invalidator adapter from the freshly
        # built principal cache so the authorization feature can drop
        # cached entries after engine-path grants/revokes without
        # importing the auth feature's cache types directly.
        principal_cache_invalidator = PrincipalCacheInvalidatorAdapter(
            auth.principal_cache
        )
        authorization = build_authorization_container(
            engine=repository.engine,
            user_authz_version=users.user_authz_version_adapter,
            user_registrar=user_registrar,
            audit=auth.audit_adapter,
            credential_verifier=auth.credential_verifier_adapter,
            principal_cache_invalidator=principal_cache_invalidator,
            promote_existing=app_settings.auth_bootstrap_promote_existing,
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
        redis_client: Any = None
        if app_settings.auth_redis_url:
            if redis_lib is None:
                raise RuntimeError(
                    "APP_AUTH_REDIS_URL is set but the `redis` package is not "
                    "installed. Install with: uv sync --extra worker"
                )
            # Bound socket waits so a slow or unreachable Redis cannot stall
            # health probes or rate-limit checks indefinitely. Liveness will
            # fail fast and report ``redis.ready=false`` instead.
            redis_client = redis_lib.Redis.from_url(
                app_settings.auth_redis_url,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
        lifespan_app.state.redis_client = redis_client

        # Expose the shared engine on app.state so the /health/ready probe
        # can run ``SELECT 1`` without reaching into any feature container.
        # The engine outlives every feature container — auth.shutdown
        # disposes it last — so this reference is safe for the whole
        # request lifetime.
        lifespan_app.state.health_db_engine = repository.engine

        # Readiness flag is set as the LAST step of startup so the probe
        # only flips green once every registry is sealed and every
        # container is attached. It is cleared as the FIRST step of
        # shutdown (below) so kubelets drop traffic the instant SIGTERM
        # lands — the contract paired with ``add-graceful-shutdown``.
        lifespan_app.state.ready = True

        try:
            yield
        finally:
            # Drop readiness FIRST so in-flight kubelet probes return 503
            # before we tear down dependent resources. The kubelet's next
            # probe fails immediately even if a slow finalizer step below
            # takes seconds to complete, so traffic is shed early.
            lifespan_app.state.ready = False
            # Shutdown order is reverse of startup so dependent resources
            # (e.g. connection pools) are closed after the services that
            # use them. Every finalizer is wrapped in ``safe_finalize``
            # so a slow Redis (or any other dependency) does not skip
            # ``engine.dispose()`` or the OTel ``provider.shutdown()``
            # — both of which leak resources if they do not run.
            safe_finalize("outbox", outbox.shutdown)
            safe_finalize("jobs", jobs.shutdown)
            safe_finalize("users", users.shutdown)
            safe_finalize("authorization", authorization.shutdown)
            # ``auth.shutdown()`` disposes the shared SQLAlchemy engine
            # (the auth container owns it), which is exactly the
            # ``engine.dispose()`` step the graceful-shutdown contract
            # requires. Kept as the last engine-touching step so any
            # earlier finalizer that still wants a session can run.
            safe_finalize("auth", auth.shutdown)
            if redis_client is not None:
                safe_finalize("redis", redis_client.close)
            # Flush the OTel ``BatchSpanProcessor`` so spans buffered by
            # the in-process queue are exported before the process exits.
            # ``shutdown_tracing`` owns the module-level provider global
            # and is idempotent — safe even when tracing was never wired.
            safe_finalize("tracing", shutdown_tracing)
            lifespan_app.state.container = None
            lifespan_app.state.redis_client = None
            lifespan_app.state.health_db_engine = None

    app.router.lifespan_context = lifespan
    return app


app = create_app()
