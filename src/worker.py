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
from typing import Any

from arq import run_worker
from arq.connections import RedisSettings

from src.features.authentication.email_templates import (
    register_authentication_email_templates,
)
from src.features.background_jobs.adapters.outbound.arq import (
    build_arq_functions,
    job_handler_logging_startup,
)
from src.features.background_jobs.composition.container import build_jobs_container
from src.features.background_jobs.composition.settings import JobsSettings
from src.features.email.composition.container import build_email_container
from src.features.email.composition.jobs import register_send_email_handler
from src.features.email.composition.settings import EmailSettings
from src.platform.config.settings import AppSettings, get_settings
from src.platform.observability import configure_logging

_logger = logging.getLogger("src.worker")


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

    jobs = build_jobs_container(jobs_settings)
    register_send_email_handler(jobs.registry, email.port)
    jobs.registry.seal()

    functions = build_arq_functions(jobs.registry)
    redis_settings = RedisSettings.from_dsn(jobs_settings.redis_url)

    class WorkerSettings:
        """arq's ``WorkerSettings`` shape, populated from composition."""

    WorkerSettings.functions = functions  # type: ignore[attr-defined]
    WorkerSettings.redis_settings = redis_settings  # type: ignore[attr-defined]
    WorkerSettings.queue_name = jobs_settings.queue_name  # type: ignore[attr-defined]
    WorkerSettings.on_startup = staticmethod(job_handler_logging_startup)  # type: ignore[attr-defined]
    return WorkerSettings


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """CLI entrypoint invoked by ``make worker``."""
    settings_cls: Any = build_worker_settings()
    run_worker(settings_cls)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
