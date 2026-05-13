"""Runtime registry of background-job handlers contributed by features.

Mirrors :class:`EmailTemplateRegistry`: each feature that owns a job
calls :meth:`register_handler` at composition time. The registry is
sealed in ``main.py`` before the application serves traffic (and in
``src/worker.py`` before the worker begins polling), after which
further registrations raise.

A handler is a sync ``Callable[[dict[str, Any]], None]``. The in-process
adapter invokes it inline; the arq adapter wraps it in an async shim so
arq's worker can ``await`` it.
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


@dataclass(slots=True)
class JobHandlerRegistry:
    """Mutable registry of job handlers owned by the background-jobs feature.

    Features register their handlers by calling
    :meth:`register_handler`; the composition root seals the registry
    after every feature has contributed.
    """

    _handlers: dict[str, JobHandler] = field(default_factory=dict)
    _sealed: bool = False

    def register_handler(self, name: str, handler: JobHandler) -> None:
        """Register ``handler`` under ``name``.

        Raises:
            RuntimeError: the registry has already been sealed.
            HandlerAlreadyRegisteredError: ``name`` is already registered.
        """
        self._guard_unsealed()
        if name in self._handlers:
            raise HandlerAlreadyRegisteredError(job_name=name)
        self._handlers[name] = handler

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
        handler = self._handlers.get(name)
        if handler is None:
            raise UnknownJobError(job_name=name)
        return handler

    def has(self, name: str) -> bool:
        """Return whether a handler is registered under ``name``."""
        return name in self._handlers

    def _guard_unsealed(self) -> None:
        if self._sealed:
            raise RuntimeError(
                "JobHandlerRegistry is sealed; register all handlers "
                "before composition completes"
            )
