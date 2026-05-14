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

import logging
import sys

import redis as redis_lib
from arq import run_worker
from arq.connections import RedisSettings
from arq.cron import CronJob
from arq.typing import StartupShutdown
from arq.worker import Function
from sqlalchemy import create_engine

from app_platform.config.settings import AppSettings, get_settings
from app_platform.observability import configure_logging
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
from features.outbox.composition.container import build_outbox_container
from features.outbox.composition.handler_dedupe import build_handler_dedupe
from features.outbox.composition.settings import OutboxSettings
from features.outbox.composition.worker import build_relay_cron_jobs

_logger = logging.getLogger("worker")


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
    # Register the send_email handler with a dedupe callable backed by
    # the outbox feature's ``processed_outbox_messages`` table — the
    # relay's at-least-once redelivery becomes effective once-per-id.
    register_send_email_handler(
        jobs.registry,
        email.port,
        dedupe=build_handler_dedupe(engine),
    )
    jobs.registry.seal()
    cron_jobs = build_relay_cron_jobs(outbox)

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
    return WorkerSettings


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """CLI entrypoint invoked by ``make worker``."""
    run_worker(build_worker_settings())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
