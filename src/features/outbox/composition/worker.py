"""Worker-side wiring for the outbox relay.

The web process never schedules the relay. The worker entrypoint
(``src/worker.py``) builds an :class:`OutboxContainer` and calls
:func:`build_relay_cron_specs` to convert the configured
``relay_interval_seconds`` into runtime-agnostic :class:`CronSpec`
descriptors.

The starter snaps the configured interval to the nearest divisor of
60 — fine for the default 5 s value, and the only divisors that
matter for an outbox cadence (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30,
60). For sub-second or non-integer intervals an operator can wire a
long-running loop instead once the production job runtime arrives
(AWS SQS + a Lambda worker, a later roadmap step); we do not ship
that today because the typical relay SLO is on the order of seconds,
not milliseconds.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from features.background_jobs.application.cron import CronSpec
from features.outbox.composition.container import OutboxContainer

_logger = logging.getLogger("features.outbox.worker")

# Divisors of 60 — the set of intervals (in seconds) that map cleanly
# onto a crontab-style ``second={...}`` specification, so a future
# scheduler can bind the descriptor without re-deriving the cadence.
_DIVISORS_OF_60 = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)


def _snap_to_divisor(interval_seconds: float) -> int:
    """Snap ``interval_seconds`` to the nearest divisor of 60.

    Picks the closest divisor; ties go to the larger one (less
    cron-pressure on the worker is the safer default). The minimum is
    1 s because crontab-style scheduling has 1 s resolution.
    """
    rounded = max(1, round(interval_seconds))
    return min(_DIVISORS_OF_60, key=lambda d: (abs(d - rounded), -d))


def build_relay_cron_specs(container: OutboxContainer) -> Sequence[CronSpec]:
    """Return the relay/prune :class:`CronSpec` descriptors.

    Empty when ``settings.enabled`` is false — the worker boot
    sequence treats the empty sequence as "no relay scheduled" and the
    worker process therefore does not poll the outbox.

    Two descriptors are returned while enabled:

    - ``outbox-relay`` — fires every ``relay_interval_seconds`` and
      drains pending rows by calling ``DispatchPending``.
    - ``outbox-prune`` — fires hourly and trims terminal
      ``delivered`` / ``failed`` rows + stale dedup marks via
      :class:`PruneOutbox`. Disjoint row set from the relay so the two
      do not contend on the same rows.
    """
    if not container.settings.enabled:
        _logger.info("event=outbox.relay.disabled APP_OUTBOX_ENABLED=false")
        return []
    interval = _snap_to_divisor(container.settings.relay_interval_seconds)
    _logger.info(
        "event=outbox.relay.scheduled interval_seconds=%d batch_size=%d worker_id=%s",
        interval,
        container.settings.claim_batch_size,
        container.settings.worker_id,
    )

    def _tick() -> None:
        # The relay is fully synchronous and self-contained; the future
        # job runtime invokes this zero-arg callable on its schedule.
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

    def _prune_tick() -> None:
        container.prune_outbox.execute(
            retention_delivered_days=settings.retention_delivered_days,
            retention_failed_days=settings.retention_failed_days,
            dedup_retention_seconds=settings.dedup_retention_seconds,
            batch_size=settings.prune_batch_size,
        )

    return [
        CronSpec(
            name="outbox-relay",
            interval_seconds=interval,
            run_at_startup=True,
            callable=_tick,
        ),
        CronSpec(
            name="outbox-prune",
            interval_seconds=3600,
            run_at_startup=False,
            callable=_prune_tick,
        ),
    ]
