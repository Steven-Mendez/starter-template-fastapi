"""Unit tests for the runtime-agnostic outbox relay/prune cron descriptors.

``arq`` was removed in ROADMAP ETAPA I step 5;
:func:`build_relay_cron_specs` now returns :class:`CronSpec`
descriptors instead of ``arq.cron.CronJob`` objects. The schedule
declarations (interval snapping, the enabled gate, the relay/prune
names) stay tested without a worker runtime — a future runtime binds
the descriptors to a real scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import cast

import pytest

from features.background_jobs.application.cron import CronSpec
from features.outbox.composition.container import OutboxContainer
from features.outbox.composition.worker import (
    _snap_to_divisor,
    build_relay_cron_specs,
)

pytestmark = pytest.mark.unit


@dataclass
class _Probe:
    """A minimal :class:`OutboxContainer` stand-in plus call recorders.

    The builder only reads ``settings.*`` and the two use cases'
    ``execute`` callables, so a typed cast over a ``SimpleNamespace``
    keeps the test free of production wiring while staying mypy-clean.
    """

    container: OutboxContainer
    relay_calls: list[None] = field(default_factory=list)
    prune_calls: list[dict[str, object]] = field(default_factory=list)


def _probe(*, enabled: bool, relay_interval_seconds: float = 5.0) -> _Probe:
    relay_calls: list[None] = []
    prune_calls: list[dict[str, object]] = []
    settings = SimpleNamespace(
        enabled=enabled,
        relay_interval_seconds=relay_interval_seconds,
        claim_batch_size=100,
        worker_id="worker-1",
        retention_delivered_days=7,
        retention_failed_days=30,
        prune_batch_size=500,
        dedup_retention_seconds=86400.0,
    )
    raw = SimpleNamespace(
        settings=settings,
        dispatch_pending=SimpleNamespace(execute=lambda: relay_calls.append(None)),
        prune_outbox=SimpleNamespace(execute=lambda **kw: prune_calls.append(kw)),
    )
    return _Probe(
        container=cast(OutboxContainer, raw),
        relay_calls=relay_calls,
        prune_calls=prune_calls,
    )


def test_disabled_outbox_yields_no_descriptors() -> None:
    specs = build_relay_cron_specs(_probe(enabled=False).container)
    assert list(specs) == []


def test_enabled_outbox_yields_relay_and_prune_descriptors() -> None:
    specs = list(build_relay_cron_specs(_probe(enabled=True).container))
    assert [s.name for s in specs] == ["outbox-relay", "outbox-prune"]
    assert all(isinstance(s, CronSpec) for s in specs)


def test_relay_descriptor_runs_at_startup_and_prune_does_not() -> None:
    relay, prune = build_relay_cron_specs(_probe(enabled=True).container)
    assert relay.name == "outbox-relay"
    assert relay.run_at_startup is True
    assert prune.name == "outbox-prune"
    assert prune.run_at_startup is False
    assert prune.interval_seconds == 3600


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (5.0, 5),
        (7.0, 6),
        (0.0, 1),
        (45.0, 60),
        (13.0, 12),
    ],
)
def test_relay_interval_snaps_to_divisor_of_60(
    configured: float, expected: int
) -> None:
    assert _snap_to_divisor(configured) == expected
    relay, _ = build_relay_cron_specs(
        _probe(enabled=True, relay_interval_seconds=configured).container
    )
    assert relay.interval_seconds == expected


def test_relay_callable_drives_dispatch_pending() -> None:
    probe = _probe(enabled=True)
    relay, prune = build_relay_cron_specs(probe.container)
    relay.callable()
    prune.callable()
    assert probe.relay_calls == [None]
    assert probe.prune_calls == [
        {
            "retention_delivered_days": 7,
            "retention_failed_days": 30,
            "dedup_retention_seconds": 86400.0,
            "batch_size": 500,
        }
    ]
