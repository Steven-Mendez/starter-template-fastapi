"""Worker-side wiring for authentication maintenance crons.

The web process never schedules these. The worker entrypoint
(``src/worker.py``) calls :func:`build_auth_maintenance_cron_jobs`
to convert the configured ``auth_token_purge_interval_minutes`` into
an arq ``cron`` registration that drives :class:`PurgeExpiredTokens`.

The cron uses arq's crontab-shaped ``minute={...}`` specification.
The starter snaps the configured interval to the nearest divisor of
60 — fine for the default (60 min) and for any operationally
meaningful tuning (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60 minutes).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from arq.cron import CronJob, cron

from features.authentication.application.use_cases.maintenance import (
    PurgeExpiredTokens,
)

_logger = logging.getLogger("features.authentication.worker")

# Divisors of 60 — the set of intervals (in minutes) that map cleanly
# onto arq's crontab-style ``minute={...}`` specification.
_DIVISORS_OF_60 = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)


def _snap_to_divisor(interval_minutes: int) -> int:
    """Snap ``interval_minutes`` to the nearest divisor of 60.

    Picks the closest divisor; ties go to the larger one (less
    cron-pressure on the worker is the safer default). The minimum is
    1 minute because arq's cron has 1-second resolution and a sub-
    minute purge cadence is never operationally useful for this job.
    """
    rounded = max(1, interval_minutes)
    return min(_DIVISORS_OF_60, key=lambda d: (abs(d - rounded), -d))


def build_auth_maintenance_cron_jobs(
    *,
    purge_expired_tokens: PurgeExpiredTokens,
    retention_days: int,
    interval_minutes: int,
) -> Sequence[CronJob]:
    """Return the arq ``cron_jobs`` list for authentication maintenance.

    Empty when ``interval_minutes <= 0`` — the operator kill switch
    for the purge job. The worker process then never schedules the
    purge, and tokens stay on disk until the setting is restored.

    Returns a one-cron list otherwise: ``auth-purge-tokens`` fires
    every ``interval_minutes`` (snapped to the nearest divisor of 60)
    and invokes ``PurgeExpiredTokens.execute(retention_days)``.
    """
    if interval_minutes <= 0:
        _logger.info(
            "event=auth.purge_expired_tokens.disabled "
            "APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES=%d",
            interval_minutes,
        )
        return []
    interval = _snap_to_divisor(interval_minutes)
    minutes = set(range(0, 60, interval))
    _logger.info(
        "event=auth.purge_expired_tokens.scheduled "
        "interval_minutes=%d retention_days=%d",
        interval,
        retention_days,
    )

    async def _tick(ctx: dict[str, Any]) -> None:  # noqa: ARG001
        # arq invokes cron jobs with a ctx kwarg; the use case is
        # fully synchronous and self-contained, so we ignore it.
        purge_expired_tokens.execute(retention_days=retention_days)

    return [
        cron(
            _tick,
            name="auth-purge-tokens",
            minute=minutes,
            unique=True,
        ),
    ]
