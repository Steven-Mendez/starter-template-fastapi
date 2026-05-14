"""Section 4.3: integration test for outbox metrics against real PostgreSQL.

Drives the end-to-end shape:

1. Seed N pending outbox rows.
2. Bind the ``app_outbox_pending_gauge`` callback to the test engine.
3. Run :class:`DispatchPending` once.
4. Assert ``app_outbox_dispatched_total{result="success"}`` increases by N
   AND the pending gauge returns 0 on the next read.

Requires Docker / testcontainers. Skipped on hosts without Docker (see
``conftest.py`` for the skip predicate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelOutboxAdapter,
)
from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.application.use_cases.dispatch_pending import DispatchPending

pytestmark = pytest.mark.integration


@dataclass(slots=True)
class _StubQueue:
    """Records enqueues; never fails."""

    enqueued: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def enqueue(self, name: str, payload: dict[str, Any]) -> None:
        self.enqueued.append((name, payload))

    def enqueue_at(
        self, name: str, payload: dict[str, Any], run_at: datetime
    ) -> None:  # pragma: no cover
        raise NotImplementedError


def _seed_pending(engine: Engine, count: int) -> None:
    with Session(engine, expire_on_commit=False) as session:
        writer = SessionSQLModelOutboxAdapter(_session=session)
        for i in range(count):
            writer.enqueue(job_name="send_email", payload={"to": f"u{i}@example.com"})
        session.commit()


def _pending_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT COUNT(*) FROM outbox_messages WHERE status = 'pending'")
            ).scalar_one()
        )


_INTEREST = {"app_outbox_dispatched_total", "app_outbox_pending_gauge"}


def _metric_values(
    reader: InMemoryMetricReader,
) -> dict[str, list[tuple[dict[str, Any], int | float]]]:
    """Collect ``{metric_name: [(attrs, value)]}`` for the in-memory reader.

    Restricted to the two metrics this test asserts against so the SDK's
    own self-monitoring histogram (``otel.sdk.metric_reader.collection.duration``,
    emitted on the second ``collect()``) is filtered out cleanly.
    """
    out: dict[str, list[tuple[dict[str, Any], int | float]]] = {}
    data = reader.get_metrics_data()
    if data is None:
        return out
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name not in _INTEREST:
                    continue
                points: list[tuple[dict[str, Any], int | float]] = []
                for pt in m.data.data_points:
                    attrs = dict(pt.attributes) if pt.attributes else {}
                    value = getattr(pt, "value", None)
                    if value is None:
                        continue
                    points.append((attrs, value))
                out.setdefault(m.name, []).extend(points)
    return out


def test_relay_tick_drops_pending_gauge_to_zero_and_increments_success_counter(
    postgres_outbox_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch N rows → success counter += N, pending gauge → 0."""
    n = 3

    # Build an isolated MeterProvider + InMemoryMetricReader so we read
    # exact values without touching the global Prometheus reader.
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    meter = provider.get_meter("integration-test")

    success_counter = meter.create_counter(name="app_outbox_dispatched_total", unit="1")

    pending_observations: list[int] = []

    def _pending_callback(_options: Any) -> list[Any]:
        from opentelemetry.metrics import Observation

        with postgres_outbox_engine.connect() as conn:
            count = int(
                conn.execute(
                    text(
                        "SELECT COUNT(*) FROM outbox_messages WHERE status = 'pending'"
                    )
                ).scalar_one()
            )
        pending_observations.append(count)
        return [Observation(count)]

    meter.create_observable_gauge(
        name="app_outbox_pending_gauge",
        callbacks=[_pending_callback],
        unit="1",
    )

    # Swap the production counter symbol so the relay records into our
    # in-memory counter for the duration of this test.
    import features.outbox.application.use_cases.dispatch_pending as module

    monkeypatch.setattr(module, "OUTBOX_DISPATCHED_TOTAL", success_counter)

    _seed_pending(postgres_outbox_engine, n)
    # Sanity: before dispatch, ``n`` rows are pending.
    pre = _metric_values(reader)
    assert pre.get("app_outbox_pending_gauge", []) != []
    # Read the most-recent observation (the SDK invokes the callback on collect).
    pre_pending_attr_values = [v for _attrs, v in pre["app_outbox_pending_gauge"]]
    assert pre_pending_attr_values[-1] == n

    use_case = DispatchPending(
        _repository=SQLModelOutboxRepository(_engine=postgres_outbox_engine),
        _job_queue=_StubQueue(),
        _batch_size=10,
        _max_attempts=5,
        _worker_id="metric-int-test",
        _retry_base=timedelta(seconds=30),
        _retry_max=timedelta(seconds=900),
    )

    report = use_case.execute()
    assert report.dispatched == n
    assert report.failed == 0
    assert report.retried == 0

    # Force a fresh collect so the observable-gauge callback fires.
    post = _metric_values(reader)

    # Counter went up by exactly ``n`` for ``result="success"``.
    success_points = [
        (attrs, val)
        for attrs, val in post.get("app_outbox_dispatched_total", [])
        if attrs == {"result": "success"}
    ]
    assert success_points, "expected at least one success data point"
    # Counters are monotonic; the last sample is the cumulative total.
    assert sum(v for _, v in success_points) == n

    # And the gauge returns 0 (no pending rows left).
    pending_points = post.get("app_outbox_pending_gauge", [])
    assert pending_points, "pending gauge should have an observation"
    last_pending = pending_points[-1][1]
    assert last_pending == 0, (
        f"pending gauge should be 0 after dispatching all rows, got {last_pending}"
    )

    # Cross-check the DB matches the gauge.
    assert _pending_count(postgres_outbox_engine) == 0
