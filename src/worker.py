"""arq worker entrypoint.

Builds the same composition root the web app uses for everything the
worker needs — the email feature (so the ``send_email`` handler can
render and dispatch templates), plus any future features that register
their handlers in their composition modules. The web app and the
worker therefore see the same set of registered jobs.

Run with ``make worker``; requires ``APP_JOBS_BACKEND=arq`` and a
reachable ``APP_JOBS_REDIS_URL``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

import redis as redis_lib
from arq import run_worker
from arq.connections import RedisSettings
from arq.cron import CronJob
from arq.typing import StartupShutdown
from arq.worker import Function
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
from features.authentication.email_templates import (
    register_authentication_email_templates,
)
from features.background_jobs.adapters.outbound.arq import (
    build_arq_functions,
    job_handler_logging_startup,
)
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
from features.outbox.composition.worker import build_relay_cron_jobs
from features.users.composition.container import build_users_container
from features.users.composition.jobs import (
    register_delete_user_assets_handler,
    register_erase_user_handler,
)

_logger = logging.getLogger("worker")

# Module-level handles used by ``on_shutdown``. They are populated by
# ``build_worker_settings`` so the shutdown hook can reach the engine
# and Redis client built during composition without arq's ``ctx`` dict
# carrying typed references.
#
# ``_RELAY_TICK_IN_FLIGHT`` is set while a ``DispatchPending.execute``
# tick is running; ``_RELAY_TICK_IDLE`` is its inverse — set whenever a
# tick is NOT running. ``on_shutdown`` awaits the idle event (bounded
# by ``APP_SHUTDOWN_TIMEOUT_SECONDS``) so an in-flight tick can commit
# or roll back cleanly before the engine is disposed and the Redis
# pool is closed. Two events instead of one ``while sleep`` poll keeps
# the hot path off the event loop and satisfies ASYNC110.
_RELAY_TICK_IN_FLIGHT: asyncio.Event | None = None
_RELAY_TICK_IDLE: asyncio.Event | None = None
_SHUTDOWN_TIMEOUT_SECONDS: float = 30.0
_ENGINE: Engine | None = None
_REDIS_CLIENT: Any | None = None


def _ensure_relay_events() -> tuple[asyncio.Event, asyncio.Event]:
    """Lazily build the relay-tick events on first use.

    ``asyncio.Event`` no longer binds to a running loop in 3.10+, so it
    is safe to construct at import time, but lazy construction lets the
    test suite reset them between scenarios without touching globals
    from the test side.
    """
    global _RELAY_TICK_IN_FLIGHT, _RELAY_TICK_IDLE  # noqa: PLW0603
    if _RELAY_TICK_IN_FLIGHT is None:
        _RELAY_TICK_IN_FLIGHT = asyncio.Event()
    if _RELAY_TICK_IDLE is None:
        _RELAY_TICK_IDLE = asyncio.Event()
        _RELAY_TICK_IDLE.set()
    return _RELAY_TICK_IN_FLIGHT, _RELAY_TICK_IDLE


def _set_shutdown_handles(
    *,
    engine: Engine,
    redis_client: Any,
    shutdown_timeout_seconds: float,
) -> None:
    """Wire the engine, Redis client, and timeout into the shutdown path.

    Extracted as a small helper so tests can clear the module-level
    handles between runs (the arq worker entrypoint is a single process,
    but the test suite invokes ``build_worker_settings`` multiple times).
    """
    global _ENGINE, _REDIS_CLIENT, _SHUTDOWN_TIMEOUT_SECONDS  # noqa: PLW0603
    _ENGINE = engine
    _REDIS_CLIENT = redis_client
    _SHUTDOWN_TIMEOUT_SECONDS = shutdown_timeout_seconds


def _wrap_relay_tick(
    tick: Callable[[dict[str, Any]], Awaitable[None]],
) -> Callable[[dict[str, Any]], Coroutine[Any, Any, None]]:
    """Wrap the relay cron's coroutine so it marks itself in-flight.

    The wrapper sets a module-level ``asyncio.Event`` while
    ``DispatchPending.execute`` is running so ``on_shutdown`` can
    ``await`` for the tick to finish (bounded by the shutdown timeout)
    before disposing the engine. The original coroutine's return value
    and exceptions pass through unchanged.
    """

    async def _instrumented(ctx: dict[str, Any]) -> None:
        in_flight, idle = _ensure_relay_events()
        in_flight.set()
        idle.clear()
        try:
            await tick(ctx)
        finally:
            in_flight.clear()
            idle.set()

    return _instrumented


async def _on_shutdown(ctx: dict[str, Any]) -> None:  # noqa: ARG001
    """arq ``on_shutdown`` hook: drain the relay, dispose pools.

    Each step is wrapped in ``try/except`` + warn log so a slow or
    broken step (e.g. an unreachable Redis) does not prevent the
    others. Order: wait for the in-flight relay tick to complete (so
    a half-claimed outbox batch commits or rolls back cleanly),
    dispose the SQLAlchemy engine, close the Redis client, and flush
    the OTel ``BatchSpanProcessor``.
    """
    in_flight = _RELAY_TICK_IN_FLIGHT
    idle = _RELAY_TICK_IDLE
    if in_flight is not None and idle is not None and in_flight.is_set():
        try:
            await asyncio.wait_for(idle.wait(), _SHUTDOWN_TIMEOUT_SECONDS)
        except TimeoutError:
            _logger.warning(
                "event=worker.shutdown.relay.tick_drain_timeout timeout_s=%.1f",
                _SHUTDOWN_TIMEOUT_SECONDS,
            )
        except Exception:
            _logger.warning("event=worker.shutdown.relay.tick_drain_failed")

    engine = _ENGINE
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            _logger.warning("event=worker.shutdown.engine.dispose_failed")

    redis_client = _REDIS_CLIENT
    if redis_client is not None:
        try:
            close = redis_client.close
            result = close()
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            _logger.warning("event=worker.shutdown.redis.close_failed")

    try:
        shutdown_tracing()
    except Exception:  # pragma: no cover — shutdown_tracing already swallows
        _logger.warning("event=worker.shutdown.tracing.shutdown_failed")


def _email_settings(app_settings: AppSettings) -> EmailSettings:
    return EmailSettings.from_app_settings(
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


def build_worker_settings() -> type:
    """Build the arq ``WorkerSettings`` class with our registered handlers.

    Exposed at module level for tests that want to assert which
    functions get wired without spinning up an actual worker.
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
    email = build_email_container(_email_settings(app_settings))
    register_authentication_email_templates(email.registry)
    email.registry.seal()

    redis_url = app_settings.jobs_redis_url or app_settings.auth_redis_url
    jobs_settings = JobsSettings.from_app_settings(
        backend=app_settings.jobs_backend,
        redis_url=redis_url,
        queue_name=app_settings.jobs_queue_name,
    )
    if jobs_settings.backend != "arq":
        raise RuntimeError(
            "Worker entrypoint requires APP_JOBS_BACKEND=arq; "
            f"got {jobs_settings.backend!r}"
        )
    if not jobs_settings.redis_url:
        raise RuntimeError(
            "APP_JOBS_REDIS_URL (or APP_AUTH_REDIS_URL) must be set for the worker"
        )

    # Share a Redis client between the rate-limit/cache layer and the
    # job-queue adapter so the worker holds exactly one connection pool.
    redis_client = redis_lib.Redis.from_url(
        jobs_settings.redis_url,
        socket_timeout=2.0,
        socket_connect_timeout=2.0,
    )
    jobs = build_jobs_container(jobs_settings, redis_client=redis_client)

    # Outbox relay: builds its own short-lived sessions against the
    # shared SQLModel engine, so we construct an engine pinned to the
    # configured DSN. The web process owns its engine through the auth
    # repository; the worker is a separate process with its own pool.
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
    # Wire the GDPR erase-user pipeline so the worker can process
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
    cron_jobs = list(build_relay_cron_jobs(outbox))
    # Instrument the ``outbox-relay`` cron so ``on_shutdown`` can wait
    # for an in-flight ``DispatchPending.execute`` tick to finish
    # (commit or rollback) before the engine is disposed. The prune
    # cron is left alone — it runs once an hour, never overlaps a
    # shutdown of practical interest, and its rows are bounded by the
    # prune batch size.
    for cron_job in cron_jobs:
        if cron_job.name == "outbox-relay":
            # arq's ``CronJob.coroutine`` is typed ``WorkerCoroutine``,
            # an alias for a ``ctx -> Coroutine`` shape; our wrapper
            # produces the structurally-equivalent ``Callable[[ctx],
            # Awaitable[None]]``. The ``cast`` keeps mypy happy without
            # importing arq's private alias.
            from typing import cast

            from arq.typing import WorkerCoroutine

            cron_job.coroutine = cast(
                "WorkerCoroutine", _wrap_relay_tick(cron_job.coroutine)
            )

    # Publish the engine, Redis client, and shutdown budget so the
    # ``on_shutdown`` hook can dispose them. ``ctx`` is the only handle
    # arq passes to ``on_shutdown``, and it carries dynamic state; the
    # composition-time references live on the module instead.
    _set_shutdown_handles(
        engine=engine,
        redis_client=redis_client,
        shutdown_timeout_seconds=app_settings.shutdown_timeout_seconds,
    )

    functions = build_arq_functions(
        jobs.registry,
        keep_result_seconds_default=jobs_settings.keep_result_seconds_default,
    )
    redis_settings = RedisSettings.from_dsn(jobs_settings.redis_url)

    class WorkerSettings:
        """arq's ``WorkerSettings`` shape, populated from composition."""

        functions: list[Function]
        cron_jobs: list[CronJob]
        redis_settings: RedisSettings
        queue_name: str
        max_jobs: int
        job_timeout: int
        keep_result: int
        on_startup: StartupShutdown
        on_shutdown: StartupShutdown | None = None

    WorkerSettings.functions = functions
    WorkerSettings.cron_jobs = list(cron_jobs)
    WorkerSettings.redis_settings = redis_settings
    WorkerSettings.queue_name = jobs_settings.queue_name
    WorkerSettings.max_jobs = jobs_settings.max_jobs
    WorkerSettings.job_timeout = jobs_settings.job_timeout_seconds
    WorkerSettings.keep_result = jobs_settings.keep_result_seconds_default
    WorkerSettings.on_startup = job_handler_logging_startup
    WorkerSettings.on_shutdown = _on_shutdown
    return WorkerSettings


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """CLI entrypoint invoked by ``make worker``."""
    run_worker(build_worker_settings())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
