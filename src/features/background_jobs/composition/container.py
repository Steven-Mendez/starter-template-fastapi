"""Composition root for the background-jobs feature.

Builds the :class:`JobHandlerRegistry`, selects the active queue
adapter based on :class:`JobsSettings.backend`, and returns a
:class:`JobsContainer` that exposes both — the registry so other
features can register their handlers during composition, and the port
so consumers can enqueue work.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import redis as redis_lib
from arq import constants as arq_constants

from features.background_jobs.adapters.outbound.arq import ArqJobQueueAdapter
from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.ports.job_queue_port import JobQueuePort
from features.background_jobs.application.registry import JobHandlerRegistry
from features.background_jobs.composition.settings import JobsSettings


@dataclass(slots=True)
class JobsContainer:
    """Bundle of the registry, port, and shutdown hook."""

    settings: JobsSettings
    registry: JobHandlerRegistry
    port: JobQueuePort
    shutdown: Callable[[], None]


def build_jobs_container(
    settings: JobsSettings,
    *,
    redis_client: redis_lib.Redis | None = None,
) -> JobsContainer:
    """Build the background-jobs feature's container.

    The registry is created empty; consumer features (e.g. the email
    feature's ``send_email`` handler) register their handlers during
    their own composition phase. The composition root calls
    ``registry.seal()`` once every feature has run.

    When ``backend=arq`` the caller MUST supply a ``redis_client``; the
    adapter does not own its connection so the shared client used by
    rate limiting and caching can be reused.
    """
    registry = JobHandlerRegistry()

    port: JobQueuePort
    owned_client: redis_lib.Redis | None = None
    if settings.backend == "in_process":
        port = InProcessJobQueueAdapter(registry=registry)
    elif settings.backend == "arq":
        if not settings.redis_url:
            raise RuntimeError(
                "APP_JOBS_REDIS_URL is required when APP_JOBS_BACKEND=arq"
            )
        client = redis_client
        if client is None:
            client = redis_lib.Redis.from_url(
                settings.redis_url,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            owned_client = client
        port = ArqJobQueueAdapter(
            registry=registry,
            redis_client=client,
            queue_name=settings.queue_name or arq_constants.default_queue_name,
        )
    else:  # pragma: no cover - guarded by JobsSettings construction
        raise RuntimeError(f"Unknown jobs backend: {settings.backend!r}")

    def _shutdown() -> None:
        if owned_client is not None:
            owned_client.close()

    return JobsContainer(
        settings=settings,
        registry=registry,
        port=port,
        shutdown=_shutdown,
    )
