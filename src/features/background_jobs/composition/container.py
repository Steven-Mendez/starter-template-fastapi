"""Composition root for the background-jobs feature.

Builds the :class:`JobHandlerRegistry`, selects the active queue
adapter based on :class:`JobsSettings.backend`, and returns a
:class:`JobsContainer` that exposes both — the registry so other
features can register their handlers during composition, and the port
so consumers can enqueue work.

``in_process`` is the only adapter. There is no production job runtime
until the AWS SQS adapter and a Lambda worker are added at a later
roadmap step (``arq`` was removed in ROADMAP ETAPA I step 5).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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


def build_jobs_container(settings: JobsSettings) -> JobsContainer:
    """Build the background-jobs feature's container.

    The registry is created empty; consumer features (e.g. the email
    feature's ``send_email`` handler) register their handlers during
    their own composition phase. The composition root calls
    ``registry.seal()`` once every feature has run.

    ``in_process`` is the only backend; it runs handlers inline at
    enqueue time and owns no external resource (so ``shutdown`` is a
    no-op). The shared Redis client used by the auth rate limiter and
    principal cache is owned by ``src/main.py``, independent of jobs.
    """
    registry = JobHandlerRegistry()

    port: JobQueuePort
    if settings.backend == "in_process":
        port = InProcessJobQueueAdapter(registry=registry)
    else:  # pragma: no cover - guarded by JobsSettings construction
        raise RuntimeError(f"Unknown jobs backend: {settings.backend!r}")

    def _shutdown() -> None:
        return

    return JobsContainer(
        settings=settings,
        registry=registry,
        port=port,
        shutdown=_shutdown,
    )
