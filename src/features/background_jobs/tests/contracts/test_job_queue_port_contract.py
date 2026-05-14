"""Behavioural contract shared by every :class:`JobQueuePort` implementation.

Each adapter under test is exercised against the same scenarios so a
new adapter can be plugged in by extending the parametrisation.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from features.background_jobs.adapters.outbound.arq import ArqJobQueueAdapter
from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.errors import UnknownJobError
from features.background_jobs.application.ports.job_queue_port import JobQueuePort
from features.background_jobs.application.registry import JobHandlerRegistry
from features.background_jobs.tests.fakes.fake_job_queue import FakeJobQueue

pytestmark = pytest.mark.unit


AdapterFactory = Callable[[JobHandlerRegistry], JobQueuePort]


def _in_process_factory(registry: JobHandlerRegistry) -> JobQueuePort:
    return InProcessJobQueueAdapter(registry=registry)


def _arq_factory(registry: JobHandlerRegistry) -> JobQueuePort:
    return ArqJobQueueAdapter(registry=registry, redis_client=fakeredis.FakeRedis())


def _fake_factory(registry: JobHandlerRegistry) -> JobQueuePort:
    return FakeJobQueue(known_jobs=registry.registered_jobs())


@pytest.fixture
def registry() -> JobHandlerRegistry:
    r = JobHandlerRegistry()
    r.register_handler("send_email", lambda payload: None)
    return r


@pytest.mark.parametrize(
    "factory",
    [_in_process_factory, _arq_factory, _fake_factory],
    ids=["in_process", "arq", "fake"],
)
def test_enqueue_succeeds_for_registered_job(
    factory: AdapterFactory, registry: JobHandlerRegistry
) -> None:
    port = factory(registry)
    port.enqueue("send_email", {"to": "a@example.com"})


@pytest.mark.parametrize(
    "factory",
    [_in_process_factory, _arq_factory, _fake_factory],
    ids=["in_process", "arq", "fake"],
)
def test_enqueue_unknown_job_raises(
    factory: AdapterFactory, registry: JobHandlerRegistry
) -> None:
    port = factory(registry)
    with pytest.raises(UnknownJobError):
        port.enqueue("never-registered", {})


# ── enqueue_at scenarios ──────────────────────────────────────────────────────

# Only the adapters that ship a scheduler are expected to support
# ``enqueue_at``. ``InProcessJobQueueAdapter`` documents itself as
# "no scheduler"; the contract pins that surface as ``NotImplementedError``
# rather than as silent failure.


def test_enqueue_at_succeeds_for_registered_job_on_scheduling_adapters(
    registry: JobHandlerRegistry,
) -> None:
    """The two scheduling-capable adapters must accept ``enqueue_at``."""
    run_at = datetime.now(UTC) + timedelta(minutes=5)
    _arq_factory(registry).enqueue_at("send_email", {"to": "a@example.com"}, run_at)
    _fake_factory(registry).enqueue_at("send_email", {"to": "a@example.com"}, run_at)


@pytest.mark.parametrize(
    "factory",
    [_arq_factory, _fake_factory],
    ids=["arq", "fake"],
)
def test_enqueue_at_unknown_job_raises(
    factory: AdapterFactory, registry: JobHandlerRegistry
) -> None:
    """Unknown job names MUST raise on the scheduling path too, not only on
    the immediate-execution path. A regression would let a producer
    enqueue a typo'd handler for the future and only fail when the
    relay tries to run it."""
    port = factory(registry)
    run_at = datetime.now(UTC) + timedelta(minutes=5)
    with pytest.raises(UnknownJobError):
        port.enqueue_at("never-registered", {}, run_at)


def test_in_process_adapter_refuses_enqueue_at(
    registry: JobHandlerRegistry,
) -> None:
    """``InProcessJobQueueAdapter`` has no scheduler and the port
    documents that adapters MAY raise — we pin
    ``NotImplementedError`` so a future composition that swaps to
    ``in_process`` for scheduled jobs fails loudly at the call site
    rather than silently dropping the job.
    """
    port = _in_process_factory(registry)
    run_at = datetime.now(UTC) + timedelta(minutes=5)
    with pytest.raises(NotImplementedError):
        port.enqueue_at("send_email", {}, run_at)
