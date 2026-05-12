"""Helpers that turn registered :data:`JobHandler` callables into arq functions.

arq invokes handlers as ``async def handler(ctx, *args, **kwargs)``. Our
registry stores sync ``Callable[[dict[str, Any]], None]``; this module
adapts between the two shapes so the worker entrypoint can hand the
list of registered handlers to ``arq.worker.run_worker`` directly.
"""

from __future__ import annotations

import logging
from typing import Any

from arq.worker import Function, func

from src.features.background_jobs.application.registry import (
    JobHandler,
    JobHandlerRegistry,
)

_logger = logging.getLogger("src.features.background_jobs.arq.worker")


def _wrap(name: str, handler: JobHandler) -> Function:
    """Wrap a sync :data:`JobHandler` as an arq :class:`Function`.

    arq's :class:`WorkerCoroutine` is a structural protocol with a
    ``(ctx, *args, **kwargs)`` shape; using that exact signature keeps
    the resulting coroutine compatible with arq's typing.
    """

    async def _runner(ctx: dict[Any, Any], *args: Any, **kwargs: Any) -> None:
        # arq calls handlers with the args/kwargs supplied at enqueue
        # time. ``ArqJobQueueAdapter`` always passes the payload as a
        # single positional argument, so unpacking it here is safe.
        del ctx, kwargs
        handler(args[0])

    _runner.__name__ = name
    return func(_runner, name=name)


def build_arq_functions(registry: JobHandlerRegistry) -> list[Function]:
    """Return the arq :class:`Function` list for every registered handler.

    The list is computed *after* every feature has registered its
    handlers (and the registry has been sealed) so the worker sees the
    same set of jobs the web process can enqueue.
    """
    return [
        _wrap(name, registry.get(name)) for name in sorted(registry.registered_jobs())
    ]


async def job_handler_logging_startup(ctx: dict[str, Any]) -> None:
    """arq ``on_startup`` hook that logs the names of every wired job.

    Wired by :mod:`src.worker` so operators can confirm at boot which
    handlers the worker will pick up.
    """
    functions: dict[str, Function] = ctx.get("functions", {})
    names = sorted(functions.keys())
    _logger.info(
        "event=jobs.worker.started count=%d jobs=%s",
        len(names),
        ",".join(names),
    )
