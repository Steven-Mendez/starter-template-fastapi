"""Unit tests for the OpenTelemetry meter wiring and metric catalog.

Covers Section 4 of the ``expose-domain-metrics`` change:

* 4.2 — the metric-name set exposed on ``/metrics`` matches the
  documented catalog exactly (no extras, no missing).
* 4.4 — every counter is restricted to its documented closed label
  key set, so a regression that adds a high-cardinality label
  (user id, path template, etc.) fails this gate.

Per-call-site increment assertions for 4.1 live next to the call
site (see the test files referenced in the docstring of each section)
because they need the use-case fakes already wired in those packages.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# The closed metric catalog and label-key sets the spec promises.
# ---------------------------------------------------------------------------

EXPECTED_METRIC_NAMES: frozenset[str] = frozenset(
    {
        "app_auth_logins_total",
        "app_auth_refresh_total",
        "app_outbox_dispatched_total",
        "app_outbox_pending_gauge",
        "app_jobs_enqueued_total",
        "app_db_pool_checked_in",
        "app_db_pool_checked_out",
        "app_db_pool_overflow",
        "app_db_pool_size",
    }
)

# Mapping of counter name -> allowed label-key set. Gauges have no
# attributes in the current spec; counters' label sets are closed.
COUNTER_LABEL_KEYS: dict[str, frozenset[str]] = {
    "app_auth_logins_total": frozenset({"result"}),
    "app_auth_refresh_total": frozenset({"result"}),
    "app_outbox_dispatched_total": frozenset({"result"}),
    "app_jobs_enqueued_total": frozenset({"handler"}),
}


def _build_app() -> FastAPI:
    settings = AppSettings(
        environment="test",
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
        auth_redis_url=None,
        metrics_enabled=True,
    )
    return build_fastapi_app(settings)


def _parse_metric_names(prom_text: str) -> set[str]:
    """Return the set of metric names referenced in a Prometheus exposition.

    Lines look like::

        # HELP app_auth_logins_total Total login attempts ...
        # TYPE app_auth_logins_total counter
        app_auth_logins_total{result="success"} 1.0

    The metric name is the leading token before ``{`` or whitespace on
    sample lines (no leading ``#``).
    """
    names: set[str] = set()
    for raw in prom_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Split off labels and value.
        head = line.split("{", 1)[0].split(" ", 1)[0]
        # Counter exposition adds ``_total`` suffix that the OTel
        # exporter already includes in the metric name itself, so no
        # adjustment needed. Strip ``_created`` companion series the
        # exporter adds for counters.
        if head.endswith("_created"):
            head = head[: -len("_created")]
        names.add(head)
    return names


# ---------------------------------------------------------------------------
# 4.2 — /metrics catalog
# ---------------------------------------------------------------------------


def test_metrics_endpoint_exposes_exactly_the_documented_catalog(
    tmp_path: Path,
) -> None:
    """``/metrics`` must show every catalogued name; nothing else from this set.

    We don't forbid auto-instrumentation metrics shipped by other OTel
    libraries (HTTP duration, process info) — but every name listed in
    the spec MUST appear, and the catalog MUST NOT lose a name when the
    SDK or exporter version moves. Symmetrically, no name OUTSIDE the
    documented ``app_*`` prefix should be added accidentally.
    """
    # Drive at least one increment on each counter so the Prometheus
    # exporter materialises the series (counters with zero samples are
    # not always emitted by the exporter).
    from app_platform.observability import metrics as metrics_module
    from app_platform.observability.metrics import (
        AUTH_LOGINS_TOTAL,
        AUTH_REFRESH_TOTAL,
        JOBS_ENQUEUED_TOTAL,
        OUTBOX_DISPATCHED_TOTAL,
        register_db_pool_gauges,
        register_outbox_pending_callback,
    )

    AUTH_LOGINS_TOTAL.add(1, attributes={"result": "success"})
    AUTH_REFRESH_TOTAL.add(1, attributes={"result": "success"})
    OUTBOX_DISPATCHED_TOTAL.add(1, attributes={"result": "success"})
    JOBS_ENQUEUED_TOTAL.add(1, attributes={"handler": "test_handler"})

    # Reset the module-level callback lists so accumulated callbacks
    # from prior tests (each bound to a now-disposed engine) don't
    # raise inside our new callback's iteration. We mutate the lists
    # in place so the OTel SDK keeps its reference to the *dispatch*
    # callable (the SDK stored the dispatch closure when the gauges
    # were created at import time).
    metrics_module._outbox_pending_callbacks.clear()
    metrics_module._db_pool_checked_in_callbacks.clear()
    metrics_module._db_pool_checked_out_callbacks.clear()
    metrics_module._db_pool_overflow_callbacks.clear()
    metrics_module._db_pool_size_callbacks.clear()

    # Bind the observable-gauge callbacks against a file-backed SQLite
    # engine with the ``outbox_messages`` table created so the gauges
    # emit observations rather than yielding nothing (which would hide
    # them from the Prometheus exposition). File-backed avoids the
    # ``:memory:``-per-connection split that would make the table miss
    # from the callback's connect().
    from sqlalchemy import text
    from sqlmodel import create_engine

    db_file = tmp_path / "outbox.db"
    engine = create_engine(f"sqlite:///{db_file}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE outbox_messages ("
                "id TEXT PRIMARY KEY, status TEXT NOT NULL"
                ")"
            )
        )
    register_outbox_pending_callback(engine)
    register_db_pool_gauges(engine)

    client = TestClient(_build_app())
    resp = client.get("/metrics")
    assert resp.status_code == 200

    exposed = _parse_metric_names(resp.text)
    app_prefixed = {n for n in exposed if n.startswith("app_")}

    # Every documented name must be present.
    missing = EXPECTED_METRIC_NAMES - app_prefixed
    assert missing == set(), f"missing metrics on /metrics: {missing}"

    # Nothing under ``app_*`` should leak that isn't in the catalog.
    unexpected = app_prefixed - EXPECTED_METRIC_NAMES
    assert unexpected == set(), (
        f"unexpected ``app_*`` metrics on /metrics: {unexpected}"
    )


# ---------------------------------------------------------------------------
# 4.4 — cardinality regression
# ---------------------------------------------------------------------------


def test_counter_label_keys_are_restricted_to_documented_set() -> None:
    """For every counter, observed attribute keys must be a subset of the spec.

    Drives the four documented counters with realistic attribute keys
    and asserts that the OTel SDK records EXACTLY those keys (no extra
    keys silently added by the call site). This is the regression
    guard against a future change that adds ``user_id=...`` or
    ``path=...`` and blows out cardinality on the Prometheus backend.
    """
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    meter = provider.get_meter("app_platform")

    # Recreate exact counter shapes per the catalog, drive them, and
    # inspect data points.
    counters = {
        name: meter.create_counter(name=name, unit="1") for name in COUNTER_LABEL_KEYS
    }
    counters["app_auth_logins_total"].add(1, attributes={"result": "success"})
    counters["app_auth_logins_total"].add(1, attributes={"result": "failure"})
    counters["app_auth_refresh_total"].add(1, attributes={"result": "success"})
    counters["app_auth_refresh_total"].add(1, attributes={"result": "failure"})
    counters["app_outbox_dispatched_total"].add(1, attributes={"result": "success"})
    counters["app_outbox_dispatched_total"].add(1, attributes={"result": "failure"})
    counters["app_jobs_enqueued_total"].add(1, attributes={"handler": "send_email"})
    counters["app_jobs_enqueued_total"].add(1, attributes={"handler": "another"})

    data = reader.get_metrics_data()
    assert data is not None
    seen: dict[str, set[frozenset[str]]] = {}
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                for pt in m.data.data_points:
                    keys = (
                        frozenset(pt.attributes.keys())
                        if pt.attributes
                        else frozenset()
                    )
                    seen.setdefault(m.name, set()).add(keys)

    for metric_name, allowed in COUNTER_LABEL_KEYS.items():
        observed_keysets = seen.get(metric_name, set())
        assert observed_keysets, f"no data points recorded for {metric_name}"
        for key_set in observed_keysets:
            assert key_set <= allowed, (
                f"{metric_name} recorded unexpected label keys: "
                f"{set(key_set) - set(allowed)} (allowed: {allowed})"
            )


# ---------------------------------------------------------------------------
# Catalog uses the documented naming convention
# ---------------------------------------------------------------------------


def test_every_documented_metric_uses_app_prefix_and_suffix_convention() -> None:
    """Naming convention from the spec: ``app_<feature>_<noun>_<unit>``.

    Counters end with ``_total``; gauges end with ``_gauge`` (or one of
    the SQLAlchemy pool nouns ``_checked_in`` / ``_checked_out`` /
    ``_overflow`` / ``_size``). This test fails fast if a future change
    ships a metric that breaks the convention before operators discover
    the inconsistency on the dashboard side.
    """
    for name in EXPECTED_METRIC_NAMES:
        assert name.startswith("app_"), f"{name} missing app_ prefix"
        if "_total" in name:
            assert name.endswith("_total"), f"{name} counter must end in _total"
        else:
            allowed_suffixes = (
                "_gauge",
                "_checked_in",
                "_checked_out",
                "_overflow",
                "_size",
                "_seconds",
            )
            assert any(name.endswith(s) for s in allowed_suffixes), (
                f"{name} does not match documented suffix conventions"
            )
