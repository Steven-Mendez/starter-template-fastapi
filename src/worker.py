"""Runtime-agnostic worker composition-root scaffold.

This builds the *same* composition root the web app uses for
everything a job runtime needs — the email feature (so the
``send_email`` handler can render and dispatch templates), the jobs /
outbox / users / file-storage containers, the registered handlers
(``send_email``, ``delete_user_assets``, ``erase_user``), and the
relay + auth-purge cron descriptors. Building it here means a future
job runtime sees exactly the set of jobs and schedules the web
process can enqueue, and composition errors still surface loudly.

There is no job runtime wired. ``arq`` (the previous worker runtime)
was removed in ROADMAP ETAPA I step 5; the production worker runtime
(AWS SQS + a Lambda worker) arrives at ROADMAP steps 26-27. Until
then ``make worker`` builds this scaffold, logs the registered
handlers and collected cron descriptors, and exits non-zero with a
clear message — the same "honest loud refusal over a silent no-op"
stance the production validator takes.

The engine-dispose / Redis-close / tracing-flush logic is kept as
plain reusable helpers (:func:`dispose_engine`, :func:`close_redis`,
:func:`flush_tracing`, :func:`drain_worker`) so the future runtime
can re-bind them as its shutdown hook without re-deriving the drain.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine, create_engine

from app_platform.config.settings import AppSettings, get_settings
from app_platform.observability import configure_logging
from app_platform.observability.tracing import shutdown_tracing
from features.authentication.adapters.outbound.auth_artifacts_cleanup import (
    SQLModelAuthArtifactsCleanupAdapter,
)
from features.authentication.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
)
from features.authentication.adapters.outbound.user_audit_reader import (
    SQLModelUserAuditReaderAdapter,
)
from features.authentication.application.use_cases.maintenance import (
    PurgeExpiredTokens,
)
from features.authentication.composition.worker import (
    build_auth_maintenance_cron_specs,
)
from features.authentication.email_templates import (
    register_authentication_email_templates,
)
from features.background_jobs.application.cron import CronSpec
from features.background_jobs.composition.container import build_jobs_container
from features.background_jobs.composition.settings import JobsSettings
from features.email.composition.container import build_email_container
from features.email.composition.jobs import register_send_email_handler
from features.email.composition.settings import EmailSettings
from features.file_storage.composition.container import build_file_storage_container
from features.file_storage.composition.settings import StorageSettings
from features.outbox.composition.container import build_outbox_container
from features.outbox.composition.handler_dedupe import build_handler_dedupe
from features.outbox.composition.settings import OutboxSettings
from features.outbox.composition.worker import build_relay_cron_specs
from features.users.composition.container import build_users_container
from features.users.composition.jobs import (
    register_delete_user_assets_handler,
    register_erase_user_handler,
)

_logger = logging.getLogger("worker")

_NO_RUNTIME_MESSAGE = (
    "No background-job runtime is wired. `arq` was removed in ROADMAP "
    "ETAPA I step 5; the production worker runtime (AWS SQS + a Lambda "
    "worker) arrives at ROADMAP steps 26-27. `make worker` will not "
    "process jobs until then."
)


def dispose_engine(engine: Engine | None) -> None:
    """Dispose the SQLAlchemy engine, swallowing and logging failures.

    Reusable drain helper: the future job runtime's shutdown hook can
    call this directly so the drain logic is declared once.
    """
    if engine is None:
        return
    try:
        engine.dispose()
    except Exception:
        _logger.warning("event=worker.shutdown.engine.dispose_failed")


def close_redis(redis_client: Any) -> None:
    """Close the Redis client (sync or async), logging failures.

    Reusable drain helper. The scaffold's ``main()`` runs the drain
    synchronously (no event loop), so an async ``close()`` is driven to
    completion via ``asyncio.run``. A future job runtime that drains
    from inside its own loop re-binds this logic with ``await``.
    """
    if redis_client is None:
        return
    try:
        close = redis_client.close
        result = close()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    except Exception:
        _logger.warning("event=worker.shutdown.redis.close_failed")


def flush_tracing() -> None:
    """Flush the OTel ``BatchSpanProcessor``, logging failures.

    Reusable drain helper for the future job runtime's shutdown hook.
    """
    try:
        shutdown_tracing()
    except Exception:  # pragma: no cover — shutdown_tracing already swallows
        _logger.warning("event=worker.shutdown.tracing.shutdown_failed")


def drain_worker(*, engine: Engine | None, redis_client: Any) -> None:
    """Run the full worker drain in shutdown order.

    Order mirrors the API lifespan finalizer: dispose the SQLAlchemy
    engine, close the Redis client, flush the tracer provider. Each
    step is independently guarded so a slow/broken step does not skip
    the others. The future job runtime re-binds this as its shutdown
    hook (after first waiting for any in-flight tick to complete,
    bounded by ``APP_SHUTDOWN_TIMEOUT_SECONDS``).
    """
    dispose_engine(engine)
    close_redis(redis_client)
    flush_tracing()


@dataclass(slots=True)
class WorkerScaffold:
    """The composition scaffold a future job runtime re-binds.

    Holds the engine + (future) Redis client the drain helpers need,
    the resolved jobs settings, the registered handler names, and the
    collected runtime-agnostic cron descriptors. No scheduler is
    attached — a later roadmap step (AWS SQS + a Lambda worker) binds
    ``cron_specs`` and the drain to a real runtime.
    """

    engine: Engine
    redis_client: Any
    jobs_settings: JobsSettings
    registered_jobs: list[str] = field(default_factory=list)
    cron_specs: tuple[CronSpec, ...] = ()
    shutdown_timeout_seconds: float = 30.0

    def drain(self) -> None:
        """Run the worker drain (the future runtime's shutdown hook)."""
        drain_worker(engine=self.engine, redis_client=self.redis_client)


def _email_settings(app_settings: AppSettings) -> EmailSettings:
    return EmailSettings.from_app_settings(
        backend=app_settings.email_backend,
        from_address=app_settings.email_from,
        console_log_bodies=app_settings.email_console_log_bodies,
    )


def build_worker_scaffold() -> WorkerScaffold:
    """Build the shared composition root + handler/cron registry.

    Exposed at module level for tests that assert which handlers and
    cron descriptors get wired without a job runtime. Composition
    errors surface here exactly as they would for the web process.
    """
    app_settings = get_settings()
    configure_logging(
        level=app_settings.log_level,
        json_format=app_settings.environment != "development",
        service_name=f"{app_settings.otel_service_name}-worker",
        service_version=app_settings.otel_service_version,
        environment=app_settings.environment,
    )

    # Build email + register authentication templates so the send_email
    # handler can render its payloads against the same templates the
    # web app uses.
    email = build_email_container(
        _email_settings(app_settings), environment=app_settings.environment
    )
    register_authentication_email_templates(email.registry)
    email.registry.seal()

    jobs_settings = JobsSettings.from_app_settings(
        backend=app_settings.jobs_backend,
    )
    jobs = build_jobs_container(jobs_settings)

    # Outbox relay: builds its own short-lived sessions against the
    # shared SQLModel engine, so we construct an engine pinned to the
    # configured DSN. The web process owns its engine through the auth
    # repository; a worker is a separate process with its own pool.
    engine = create_engine(
        app_settings.postgresql_dsn,
        pool_pre_ping=app_settings.db_pool_pre_ping,
        pool_size=app_settings.db_pool_size,
        max_overflow=app_settings.db_max_overflow,
        pool_recycle=app_settings.db_pool_recycle_seconds,
    )
    outbox = build_outbox_container(
        OutboxSettings.from_app_settings(app_settings),
        engine=engine,
        job_queue=jobs.port,
    )
    # The worker also needs the users container so the
    # ``delete_user_assets`` handler has a wired
    # ``UserAssetsCleanupPort`` to invoke. The container builds an
    # adapter that walks the per-user prefix on ``FileStoragePort``.
    file_storage = build_file_storage_container(
        StorageSettings.from_app_settings(app_settings)
    )
    users = build_users_container(
        engine=engine,
        file_storage=file_storage.port,
        outbox_uow=outbox.unit_of_work,
    )
    # Register the send_email handler with a dedupe callable backed by
    # the outbox feature's ``processed_outbox_messages`` table — the
    # relay's at-least-once redelivery becomes effective once-per-id.
    register_send_email_handler(
        jobs.registry,
        email.port,
        dedupe=build_handler_dedupe(engine),
    )
    register_delete_user_assets_handler(
        jobs.registry,
        users.user_assets_cleanup,
        dedupe=build_handler_dedupe(engine),
    )
    # Wire the GDPR erase-user pipeline so a future runtime can process
    # ``erase_user`` outbox rows. The worker needs its own auth
    # repository to back the audit-reader and artifacts-cleanup
    # adapters; the web process owns a separate one (its connection
    # pool is distinct).
    auth_repository_for_worker = SQLModelAuthRepository.from_engine(engine)
    users.wire_erase_user(
        auth_artifacts=SQLModelAuthArtifactsCleanupAdapter(engine=engine),
        audit_reader=SQLModelUserAuditReaderAdapter(
            repository=auth_repository_for_worker
        ),
        outbox_uow=outbox.unit_of_work,
        file_storage=file_storage.port,
    )
    if users.erase_user is None:
        raise RuntimeError("EraseUser was not wired into the users container")
    register_erase_user_handler(
        jobs.registry,
        users.erase_user,
        dedupe=build_handler_dedupe(engine),
    )
    jobs.registry.seal()

    cron_specs: list[CronSpec] = list(build_relay_cron_specs(outbox))
    # Authentication maintenance crons: ``auth-purge-tokens`` sweeps
    # expired refresh and internal token rows so neither table grows
    # without bound. Disabled when the operator sets
    # ``APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES=0`` (kill switch). The
    # use case operates against the worker's auth repository (same
    # engine the relay uses) so it shares the connection pool.
    purge_expired_tokens = PurgeExpiredTokens(
        _repository=auth_repository_for_worker,
    )
    cron_specs.extend(
        build_auth_maintenance_cron_specs(
            purge_expired_tokens=purge_expired_tokens,
            retention_days=app_settings.auth_token_retention_days,
            interval_minutes=app_settings.auth_token_purge_interval_minutes,
        )
    )

    # No job runtime owns a Redis client here: the previous arq adapter
    # did, but the in-process adapter does not. The drain helper still
    # takes a ``redis_client`` so the future runtime can pass its own.
    return WorkerScaffold(
        engine=engine,
        redis_client=None,
        jobs_settings=jobs_settings,
        registered_jobs=sorted(jobs.registry.registered_jobs()),
        cron_specs=tuple(cron_specs),
        shutdown_timeout_seconds=app_settings.shutdown_timeout_seconds,
    )


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """CLI entrypoint invoked by ``make worker``.

    Builds the scaffold (so composition errors still surface loudly),
    logs the registered handlers + collected cron descriptors, then
    exits non-zero stating no job runtime is wired. The future job
    runtime (AWS SQS + a Lambda worker, ROADMAP steps 26-27) replaces
    this exit with its event loop.
    """
    scaffold = build_worker_scaffold()
    _logger.info(
        "event=worker.scaffold.built backend=%s handlers=%d jobs=%s",
        scaffold.jobs_settings.backend,
        len(scaffold.registered_jobs),
        ",".join(scaffold.registered_jobs),
    )
    for spec in scaffold.cron_specs:
        _logger.info(
            "event=worker.scaffold.cron name=%s interval_seconds=%d run_at_startup=%s",
            spec.name,
            spec.interval_seconds,
            spec.run_at_startup,
        )
    # The composition root is intact; release the resources the
    # scaffold opened (no runtime owns them) before the honest exit.
    scaffold.drain()
    _logger.error("event=worker.no_runtime %s", _NO_RUNTIME_MESSAGE)
    print(_NO_RUNTIME_MESSAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
