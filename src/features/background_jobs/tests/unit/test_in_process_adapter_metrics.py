"""Section 4.1: ``InProcessJobQueueAdapter.enqueue`` updates the jobs counter.

The counter is labelled by ``handler`` (the job name). The label is
bounded by the :class:`JobHandlerRegistry`, so it is closed-set and
safe for Prometheus cardinality.
"""

from __future__ import annotations

import pytest

from app_platform.tests.unit.observability._metric_helpers import (
    CounterHarness,
    install_counter,
)
from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.errors import UnknownJobError
from features.background_jobs.application.registry import JobHandlerRegistry

pytestmark = pytest.mark.unit


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> CounterHarness:
    return install_counter(
        monkeypatch,
        name="app_jobs_enqueued_total",
        attr_name="JOBS_ENQUEUED_TOTAL",
        modules=[
            "app_platform.observability.metrics",
            "features.background_jobs.adapters.outbound.in_process.adapter",
        ],
    )


def test_enqueue_increments_for_registered_handler(
    counter: CounterHarness,
) -> None:
    registry = JobHandlerRegistry()
    registry.register_handler("send_email", lambda payload: None)
    adapter = InProcessJobQueueAdapter(registry=registry)

    adapter.enqueue("send_email", {"to": "a@example.com"})

    assert counter.total(handler="send_email") == 1


def test_enqueue_increments_per_call(counter: CounterHarness) -> None:
    """Three enqueues of the same handler aggregate to 3 on the ``handler`` key."""
    registry = JobHandlerRegistry()
    registry.register_handler("send_email", lambda payload: None)
    adapter = InProcessJobQueueAdapter(registry=registry)

    for _ in range(3):
        adapter.enqueue("send_email", {})

    assert counter.total(handler="send_email") == 3


def test_enqueue_uses_handler_name_label(counter: CounterHarness) -> None:
    """Distinct handlers produce distinct label values."""
    registry = JobHandlerRegistry()
    registry.register_handler("send_email", lambda payload: None)
    registry.register_handler("dispatch_outbox", lambda payload: None)
    adapter = InProcessJobQueueAdapter(registry=registry)

    adapter.enqueue("send_email", {})
    adapter.enqueue("dispatch_outbox", {})
    adapter.enqueue("send_email", {})

    assert counter.total(handler="send_email") == 2
    assert counter.total(handler="dispatch_outbox") == 1


def test_unknown_job_does_not_increment_counter(counter: CounterHarness) -> None:
    """Unknown jobs raise BEFORE incrementing; the counter never sees them."""
    registry = JobHandlerRegistry()
    adapter = InProcessJobQueueAdapter(registry=registry)

    with pytest.raises(UnknownJobError):
        adapter.enqueue("never-registered", {})

    # No data points were ever recorded.
    assert counter.points() == []


def test_in_process_counter_uses_only_handler_attribute(
    counter: CounterHarness,
) -> None:
    """4.4 regression: only the ``handler`` label key may be present."""
    registry = JobHandlerRegistry()
    registry.register_handler("send_email", lambda payload: None)
    adapter = InProcessJobQueueAdapter(registry=registry)

    adapter.enqueue("send_email", {})

    for attrs, _ in counter.points():
        assert set(attrs.keys()) == {"handler"}, (
            f"jobs counter emitted unexpected label keys: {set(attrs.keys())}"
        )
