"""Worker-side wiring for authentication maintenance crons.

The web process never schedules these. The worker entrypoint
(``src/worker.py``) calls :func:`build_auth_maintenance_cron_specs`
to convert the configured ``auth_token_purge_interval_minutes`` into
a runtime-agnostic :class:`CronSpec` descriptor that drives
:class:`PurgeExpiredTokens`.

The starter snaps the configured interval to the nearest divisor of
60 — fine for the default (60 min) and for any operationally
meaningful tuning (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60 minutes).
A future job runtime (AWS SQS + a Lambda worker, a later roadmap
step) binds the descriptor to a real scheduler.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from features.authentication.application.use_cases.maintenance import (
    PurgeExpiredTokens,
)
from features.background_jobs.application.cron import CronSpec

_logger = logging.getLogger("features.authentication.worker")

# Divisors of 60 — the set of intervals (in minutes) that map cleanly
# onto a crontab-style ``minute={...}`` specification, so a future
# scheduler can bind the descriptor without re-deriving the cadence.
_DIVISORS_OF_60 = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)


def _snap_to_divisor(interval_minutes: int) -> int:
    """Snap ``interval_minutes`` to the nearest divisor of 60.

    Picks the closest divisor; ties go to the larger one (less
    cron-pressure on the worker is the safer default). The minimum is
    1 minute because a sub-minute purge cadence is never operationally
    useful for this job.
    """
    rounded = max(1, interval_minutes)
    return min(_DIVISORS_OF_60, key=lambda d: (abs(d - rounded), -d))


def build_auth_maintenance_cron_specs(
    *,
    purge_expired_tokens: PurgeExpiredTokens,
    retention_days: int,
    interval_minutes: int,
) -> Sequence[CronSpec]:
    """Return the authentication-maintenance :class:`CronSpec` list.

    Empty when ``interval_minutes <= 0`` — the operator kill switch
    for the purge job. The worker process then never schedules the
    purge, and tokens stay on disk until the setting is restored.

    Returns a one-descriptor list otherwise: ``auth-purge-tokens``
    fires every ``interval_minutes`` (snapped to the nearest divisor
    of 60) and invokes ``PurgeExpiredTokens.execute(retention_days)``.
    """
    if interval_minutes <= 0:
        _logger.info(
            "event=auth.purge_expired_tokens.disabled "
            "APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES=%d",
            interval_minutes,
        )
        return []
    interval = _snap_to_divisor(interval_minutes)
    _logger.info(
        "event=auth.purge_expired_tokens.scheduled "
        "interval_minutes=%d retention_days=%d",
        interval,
        retention_days,
    )

    def _tick() -> None:
        # The use case is fully synchronous and self-contained; the
        # future job runtime invokes this zero-arg callable on its
        # schedule.
        purge_expired_tokens.execute(retention_days=retention_days)

    return [
        CronSpec(
            name="auth-purge-tokens",
            interval_seconds=interval * 60,
            run_at_startup=False,
            callable=_tick,
        ),
    ]
