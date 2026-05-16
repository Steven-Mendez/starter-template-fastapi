"""Unit tests for the runtime-agnostic auth-maintenance cron descriptor.

``arq`` was removed in ROADMAP ETAPA I step 5;
:func:`build_auth_maintenance_cron_specs` now returns a
:class:`CronSpec` instead of an ``arq.cron.CronJob``. The schedule
declaration (interval snapping, the ``interval_minutes <= 0`` kill
switch, the ``auth-purge-tokens`` name) stays tested without a worker
runtime — a future runtime binds the descriptor to a real scheduler.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from features.authentication.application.use_cases.maintenance import (
    PurgeExpiredTokens,
)
from features.authentication.composition.worker import (
    _snap_to_divisor,
    build_auth_maintenance_cron_specs,
)
from features.background_jobs.application.cron import CronSpec

pytestmark = pytest.mark.unit


def _purge_stub() -> tuple[PurgeExpiredTokens, list[int]]:
    calls: list[int] = []
    stub = SimpleNamespace(
        execute=lambda *, retention_days: calls.append(retention_days)
    )
    return cast(PurgeExpiredTokens, stub), calls


@pytest.mark.parametrize("interval_minutes", [0, -1, -60])
def test_kill_switch_yields_no_descriptor(interval_minutes: int) -> None:
    purge, _ = _purge_stub()
    specs = build_auth_maintenance_cron_specs(
        purge_expired_tokens=purge,
        retention_days=7,
        interval_minutes=interval_minutes,
    )
    assert list(specs) == []


def test_enabled_yields_one_purge_descriptor() -> None:
    purge, _ = _purge_stub()
    specs = list(
        build_auth_maintenance_cron_specs(
            purge_expired_tokens=purge,
            retention_days=7,
            interval_minutes=60,
        )
    )
    assert len(specs) == 1
    spec = specs[0]
    assert isinstance(spec, CronSpec)
    assert spec.name == "auth-purge-tokens"
    assert spec.run_at_startup is False


@pytest.mark.parametrize(
    ("configured_minutes", "expected_minutes"),
    [
        (60, 60),
        (7, 6),
        (1, 1),
        (45, 60),
        (13, 12),
    ],
)
def test_interval_snaps_to_divisor_of_60_and_is_seconds(
    configured_minutes: int, expected_minutes: int
) -> None:
    purge, _ = _purge_stub()
    assert _snap_to_divisor(configured_minutes) == expected_minutes
    (spec,) = build_auth_maintenance_cron_specs(
        purge_expired_tokens=purge,
        retention_days=7,
        interval_minutes=configured_minutes,
    )
    # The descriptor carries seconds (snapped minutes * 60) so the
    # future scheduler binds it uniformly with the outbox descriptors.
    assert spec.interval_seconds == expected_minutes * 60


def test_callable_drives_purge_with_retention_days() -> None:
    purge, calls = _purge_stub()
    (spec,) = build_auth_maintenance_cron_specs(
        purge_expired_tokens=purge,
        retention_days=14,
        interval_minutes=30,
    )
    spec.callable()
    assert calls == [14]
