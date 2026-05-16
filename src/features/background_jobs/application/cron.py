"""Runtime-agnostic recurring-job descriptor.

The two per-feature cron modules (``features.outbox.composition.worker``
and ``features.authentication.composition.worker``) declare their
recurring schedules as :class:`CronSpec` descriptors instead of binding
them to a specific scheduler. ``src/worker.py`` collects the descriptors
so the schedule is *declared once* and unit-tested without a worker
runtime; a future job runtime (AWS SQS + a Lambda worker, a later
roadmap step) binds them to a real scheduler.

This lives in the background-jobs *application* layer (no framework
imports). Other features' composition modules legitimately import
background-jobs application symbols (``JobQueuePort``,
``JobHandlerRegistry``); :class:`CronSpec` follows that same edge.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CronSpec:
    """A single recurring job, declared independently of any scheduler.

    ``interval_seconds`` is already snapped to a divisor of 60 by the
    builder, so a future scheduler can map it directly onto a
    crontab-shaped ``second=`` / ``minute=`` specification without
    re-deriving it. ``callable`` is the synchronous tick — zero-arg, no
    scheduler context — so binding it to any runtime is trivial.
    """

    name: str
    interval_seconds: int
    run_at_startup: bool
    callable: Callable[[], None]
