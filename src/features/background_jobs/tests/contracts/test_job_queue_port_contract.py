"""Behavioural contract shared by every :class:`JobQueuePort` implementation.

Each adapter under test is exercised against the same scenarios so a
new adapter can be plugged in by extending the parametrisation.
"""

from __future__ import annotations

from typing import Callable

import fakeredis
import pytest

from src.features.background_jobs.adapters.outbound.arq import ArqJobQueueAdapter
from src.features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from src.features.background_jobs.application.errors import UnknownJobError
from src.features.background_jobs.application.ports.job_queue_port import JobQueuePort
from src.features.background_jobs.application.registry import JobHandlerRegistry
from src.features.background_jobs.tests.fakes.fake_job_queue import FakeJobQueue

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
