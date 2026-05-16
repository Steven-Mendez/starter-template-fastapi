"""Runtime registry of background-job handlers contributed by features.

Mirrors :class:`EmailTemplateRegistry`: each feature that owns a job
calls :meth:`register_handler` at composition time. The registry is
sealed in ``main.py`` before the application serves traffic (and in
``src/worker.py``'s composition scaffold), after which further
registrations raise.

A handler is a sync ``Callable[[dict[str, Any]], None]``. The in-process
adapter invokes it inline. The future production job runtime (AWS SQS +
a Lambda worker, a later roadmap step) re-binds the same registry at its
own entrypoint.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from features.background_jobs.application.errors import (
    HandlerAlreadyRegisteredError,
    UnknownJobError,
)

JobHandler = Callable[[dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class JobHandlerEntry:
    """Registered handler plus its optional per-handler runtime tunables.

    ``keep_result_seconds`` is a result-retention hint a future
    serializing job runtime (AWS SQS + a Lambda worker, a later roadmap
    step) may honour; the in-process adapter ignores it (it runs the
    handler inline and keeps no result record).
    """

    handler: JobHandler
    keep_result_seconds: int | None = None


@dataclass(slots=True)
class JobHandlerRegistry:
    """Mutable registry of job handlers owned by the background-jobs feature.

    Features register their handlers by calling
    :meth:`register_handler`; the composition root seals the registry
    after every feature has contributed.
    """

    _handlers: dict[str, JobHandlerEntry] = field(default_factory=dict)
    _sealed: bool = False

    def register_handler(
        self,
        name: str,
        handler: JobHandler,
        *,
        keep_result_seconds: int | None = None,
    ) -> None:
        """Register ``handler`` under ``name``.

        Pass ``keep_result_seconds`` only when the job's result must outlive
        the registry-wide default (e.g. a payment-idempotency replay window).

        Raises:
            RuntimeError: the registry has already been sealed.
            HandlerAlreadyRegisteredError: ``name`` is already registered.
        """
        self._guard_unsealed()
        if name in self._handlers:
            raise HandlerAlreadyRegisteredError(job_name=name)
        self._handlers[name] = JobHandlerEntry(
            handler=handler, keep_result_seconds=keep_result_seconds
        )

    def seal(self) -> None:
        """Freeze the registry; further registrations raise ``RuntimeError``."""
        self._sealed = True

    @property
    def sealed(self) -> bool:
        return self._sealed

    def registered_jobs(self) -> set[str]:
        """Return the set of registered job names."""
        return set(self._handlers)

    def get(self, name: str) -> JobHandler:
        """Return the handler registered under ``name``.

        Raises:
            UnknownJobError: no handler is registered for ``name``.
        """
        entry = self._handlers.get(name)
        if entry is None:
            raise UnknownJobError(job_name=name)
        return entry.handler

    def get_entry(self, name: str) -> JobHandlerEntry:
        """Return the full registry entry (handler + tunables) for ``name``.

        Raises:
            UnknownJobError: no handler is registered for ``name``.
        """
        entry = self._handlers.get(name)
        if entry is None:
            raise UnknownJobError(job_name=name)
        return entry

    def entries(self) -> dict[str, JobHandlerEntry]:
        """Return a copy of the registered (name -> entry) mapping."""
        return dict(self._handlers)

    def has(self, name: str) -> bool:
        """Return whether a handler is registered under ``name``."""
        return name in self._handlers

    def _guard_unsealed(self) -> None:
        if self._sealed:
            raise RuntimeError(
                "JobHandlerRegistry is sealed; register all handlers "
                "before composition completes"
            )
