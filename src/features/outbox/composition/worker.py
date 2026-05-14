"""Worker-side wiring for the outbox relay.

The web process never schedules the relay. The worker entrypoint
(``src/worker.py``) builds an :class:`OutboxContainer` and calls
:func:`build_relay_cron_jobs` to convert the configured
``relay_interval_seconds`` into an arq ``cron`` registration.

arq's ``cron`` scheduler fires on a crontab-shaped specification
(``second={0, 5, 10, ...}``). The starter snaps the configured
interval to the nearest divisor of 60 — fine for the default 5 s
value, and the only divisors that matter for an outbox cadence
(1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60). For sub-second or
non-integer intervals an operator can wire a long-running async
loop instead; we do not ship that today because the typical relay
SLO is on the order of seconds, not milliseconds.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from arq.cron import CronJob, cron

from features.outbox.composition.container import OutboxContainer

_logger = logging.getLogger("features.outbox.worker")

# Divisors of 60 — the set of intervals (in seconds) that map cleanly
# onto arq's crontab-style ``second={...}`` specification.
_DIVISORS_OF_60 = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)


def _snap_to_divisor(interval_seconds: float) -> int:
    """Snap ``interval_seconds`` to the nearest divisor of 60.

    Picks the closest divisor; ties go to the larger one (less
    cron-pressure on the worker is the safer default). The minimum is
    1 s because arq's cron has 1 s resolution.
    """
    rounded = max(1, round(interval_seconds))
    return min(_DIVISORS_OF_60, key=lambda d: (abs(d - rounded), -d))


def build_relay_cron_jobs(container: OutboxContainer) -> Sequence[CronJob]:
    """Return the arq ``cron_jobs`` list for the worker entrypoint.

    Empty when ``settings.enabled`` is false — the web/worker boot
    sequence treats the empty list as "no relay scheduled" and the
    worker process therefore does not poll the outbox.

    Two crons are registered while enabled:

    - ``outbox-relay`` — fires every ``relay_interval_seconds`` and
      drains pending rows by calling ``DispatchPending``.
    - ``outbox-prune`` — fires hourly (minute 0) and trims terminal
      ``delivered`` / ``failed`` rows + stale dedup marks via
      :class:`PruneOutbox`. Disjoint row set from the relay so the two
      do not contend on the same rows.
    """
    if not container.settings.enabled:
        _logger.info("event=outbox.relay.disabled APP_OUTBOX_ENABLED=false")
        return []
    interval = _snap_to_divisor(container.settings.relay_interval_seconds)
    seconds = set(range(0, 60, interval))
    _logger.info(
        "event=outbox.relay.scheduled interval_seconds=%d batch_size=%d worker_id=%s",
        interval,
        container.settings.claim_batch_size,
        container.settings.worker_id,
    )

    async def _tick(ctx: dict[str, Any]) -> None:  # noqa: ARG001
        # arq invokes cron jobs with a ctx kwarg; the relay is fully
        # synchronous and self-contained, so we ignore it.
        container.dispatch_pending.execute()

    settings = container.settings
    _logger.info(
        "event=outbox.prune.scheduled retention_delivered_days=%d "
        "retention_failed_days=%d prune_batch_size=%d "
        "dedup_retention_seconds=%.1f",
        settings.retention_delivered_days,
        settings.retention_failed_days,
        settings.prune_batch_size,
        settings.dedup_retention_seconds,
    )

    async def _prune_tick(ctx: dict[str, Any]) -> None:  # noqa: ARG001
        container.prune_outbox.execute(
            retention_delivered_days=settings.retention_delivered_days,
            retention_failed_days=settings.retention_failed_days,
            dedup_retention_seconds=settings.dedup_retention_seconds,
            batch_size=settings.prune_batch_size,
        )

    return [
        cron(
            _tick,
            name="outbox-relay",
            second=seconds,
            run_at_startup=True,
            unique=True,
        ),
        cron(
            _prune_tick,
            name="outbox-prune",
            minute={0},
            unique=True,
        ),
    ]
