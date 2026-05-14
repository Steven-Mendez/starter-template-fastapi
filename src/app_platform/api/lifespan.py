"""Helpers for the FastAPI ``lifespan`` finalizer.

The lifespan teardown runs a sequence of best-effort shutdown steps
(disposing the engine, closing Redis, flushing OTel). Each step is
independent: a slow or failing step MUST NOT prevent the others from
running, or the process leaks file descriptors and dropped spans on
the way out.

:func:`safe_finalize` is the wrapper that gives every step that
guarantee — it runs the callable, swallows any exception, and emits a
single warn log identifying which step failed so operators can see
shutdown-time errors without losing the visibility of the surrounding
finalizers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

_logger = logging.getLogger(__name__)


def safe_finalize(label: str, fn: Callable[[], object]) -> None:
    """Run ``fn`` as a lifespan-finalizer step, logging failures.

    Used by both :mod:`main` (the FastAPI app's lifespan) and the
    worker entrypoint to keep the shutdown path resilient to a single
    failing dependency. Returns ``None`` regardless of ``fn``'s return
    value; the caller never reads it.
    """
    try:
        fn()
    except Exception:
        _logger.warning("event=lifespan.shutdown.step.failed step=%s", label)
