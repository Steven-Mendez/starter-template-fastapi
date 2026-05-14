"""Section 4.1: ``ArqJobQueueAdapter.enqueue`` increments ``app_jobs_enqueued_total``.

The arq adapter writes directly to a Redis-shaped backend (``fakeredis``
in tests); the metric increment lives in the same enqueue path as the
in-process adapter and is gated by the same ``UnknownJobError`` check.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from app_platform.tests.unit.observability._metric_helpers import (
    CounterHarness,
    install_counter,
)
from features.background_jobs.adapters.outbound.arq import ArqJobQueueAdapter
from features.background_jobs.application.errors import UnknownJobError
from features.background_jobs.application.registry import JobHandlerRegistry

pytestmark = pytest.mark.unit


@pytest.fixture
def registry() -> JobHandlerRegistry:
    r = JobHandlerRegistry()
    r.register_handler("send_email", lambda payload: None)
    r.register_handler("dispatch_outbox", lambda payload: None)
    return r


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis()


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> CounterHarness:
    return install_counter(
        monkeypatch,
        name="app_jobs_enqueued_total",
        attr_name="JOBS_ENQUEUED_TOTAL",
        modules=[
            "app_platform.observability.metrics",
            "features.background_jobs.adapters.outbound.arq.adapter",
        ],
    )


def test_arq_enqueue_increments_handler_label(
    registry: JobHandlerRegistry,
    redis_client: fakeredis.FakeRedis,
    counter: CounterHarness,
) -> None:
    adapter = ArqJobQueueAdapter(registry=registry, redis_client=redis_client)

    adapter.enqueue("send_email", {"to": "a@e.com"})

    assert counter.total(handler="send_email") == 1


def test_arq_enqueue_distinguishes_handlers(
    registry: JobHandlerRegistry,
    redis_client: fakeredis.FakeRedis,
    counter: CounterHarness,
) -> None:
    adapter = ArqJobQueueAdapter(registry=registry, redis_client=redis_client)

    adapter.enqueue("send_email", {})
    adapter.enqueue("dispatch_outbox", {})
    adapter.enqueue("send_email", {})

    assert counter.total(handler="send_email") == 2
    assert counter.total(handler="dispatch_outbox") == 1


def test_arq_unknown_job_does_not_increment_counter(
    redis_client: fakeredis.FakeRedis,
    counter: CounterHarness,
) -> None:
    """Unknown jobs raise BEFORE the increment is recorded."""
    empty_registry = JobHandlerRegistry()
    adapter = ArqJobQueueAdapter(registry=empty_registry, redis_client=redis_client)

    with pytest.raises(UnknownJobError):
        adapter.enqueue("nope", {})

    assert counter.points() == []


def test_arq_enqueue_at_does_not_increment_immediate_counter(
    registry: JobHandlerRegistry,
    redis_client: fakeredis.FakeRedis,
    counter: CounterHarness,
) -> None:
    """``enqueue_at`` is scheduled execution — the metric tracks immediate
    enqueues only. The instrumented call site is ``enqueue``; the
    scheduled path is intentionally NOT counted here to keep ``handler``
    semantics consistent between adapters (the in-process adapter has no
    scheduled path).
    """
    adapter = ArqJobQueueAdapter(registry=registry, redis_client=redis_client)
    adapter.enqueue_at("send_email", {}, datetime.now(UTC) + timedelta(hours=1))
    assert counter.points() == []


def test_arq_counter_uses_only_handler_attribute(
    registry: JobHandlerRegistry,
    redis_client: fakeredis.FakeRedis,
    counter: CounterHarness,
) -> None:
    """4.4 regression at the arq call site."""
    adapter = ArqJobQueueAdapter(registry=registry, redis_client=redis_client)
    adapter.enqueue("send_email", {})

    for attrs, _ in counter.points():
        assert set(attrs.keys()) == {"handler"}, (
            f"arq jobs counter emitted unexpected label keys: {set(attrs.keys())}"
        )
