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

from features.background_jobs.application.registry import (
    JobHandler,
    JobHandlerRegistry,
)

_logger = logging.getLogger("features.background_jobs.arq.worker")


def _wrap(
    name: str, handler: JobHandler, *, keep_result_seconds: int | None
) -> Function:
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
        payload: dict[str, Any] = args[0]
        # Extract the W3C trace carrier the relay injected under
        # ``__trace`` (if any) and attach it before invoking the
        # handler so the handler's spans become children of the
        # originating request's trace. Detach in ``finally`` so the
        # active OTel context is restored even when the handler
        # raises — arq's executor reuses worker coroutines across
        # jobs and a leaked context token would taint the next one.
        from opentelemetry import context as otel_context
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        carrier = payload.get("__trace") or {}
        otel_ctx = TraceContextTextMapPropagator().extract(carrier=carrier)
        token = otel_context.attach(otel_ctx)
        try:
            handler(payload)
        finally:
            otel_context.detach(token)

    _runner.__name__ = name
    return func(_runner, name=name, keep_result=keep_result_seconds)


def build_arq_functions(
    registry: JobHandlerRegistry,
    *,
    keep_result_seconds_default: int = 300,
) -> list[Function]:
    """Return the arq :class:`Function` list for every registered handler.

    The list is computed *after* every feature has registered its
    handlers (and the registry has been sealed) so the worker sees the
    same set of jobs the web process can enqueue.
    """
    functions: list[Function] = []
    for name in sorted(registry.registered_jobs()):
        entry = registry.get_entry(name)
        keep = (
            entry.keep_result_seconds
            if entry.keep_result_seconds is not None
            else keep_result_seconds_default
        )
        functions.append(_wrap(name, entry.handler, keep_result_seconds=keep))
    return functions


async def job_handler_logging_startup(ctx: dict[str, Any]) -> None:
    """arq ``on_startup`` hook that logs the names of every wired job.

    Wired by :mod:`worker` so operators can confirm at boot which
    handlers the worker will pick up.
    """
    functions: dict[str, Function] = ctx.get("functions", {})
    names = sorted(functions.keys())
    _logger.info(
        "event=jobs.worker.started count=%d jobs=%s",
        len(names),
        ",".join(names),
    )
