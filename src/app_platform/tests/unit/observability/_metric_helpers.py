"""Test helpers for asserting against OTel metric instruments.

The production code captures counter instruments at import time::

    from app_platform.observability.metrics import AUTH_LOGINS_TOTAL

so any call to :func:`reset_meter_provider` after import does NOT re-bind
the instrument references already held by the use case modules. The
helpers below sidestep that by:

1. Building a fresh :class:`MeterProvider` wired to an
   :class:`InMemoryMetricReader`.
2. Creating fresh counter instruments on that provider.
3. Monkey-patching the counter symbol on every module that has imported
   it (the metrics module itself AND each call-site module) so the
   production code increments the in-memory instrument under test.

This keeps assertions exact: each test owns its own reader, so cross-
test bleed is impossible.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pytest
from opentelemetry.metrics import Counter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader


@dataclass(slots=True)
class CounterHarness:
    """A fresh counter wired to a fresh in-memory reader."""

    reader: InMemoryMetricReader
    counter: Counter
    metric_name: str

    def points(self) -> list[tuple[dict[str, Any], int | float]]:
        """Return ``[(attrs_dict, value), ...]`` for the harness's counter.

        Filters to ``self.metric_name`` so the SDK's own
        self-monitoring instruments (e.g.
        ``otel.sdk.metric_reader.collection.duration`` Histogram, which
        appears on the second ``collect()`` call) don't leak into the
        assertion.
        """
        data = self.reader.get_metrics_data()
        rows: list[tuple[dict[str, Any], int | float]] = []
        if data is None:
            return rows
        for rm in data.resource_metrics:
            for sm in rm.scope_metrics:
                for m in sm.metrics:
                    if m.name != self.metric_name:
                        continue
                    for pt in m.data.data_points:
                        attrs = dict(pt.attributes) if pt.attributes else {}
                        # The harness's counters are all Sum/NumberDataPoint;
                        # skip anything else (SDK self-monitoring histograms
                        # would lack ``.value`` here).
                        value = getattr(pt, "value", None)
                        if value is None:
                            continue
                        rows.append((attrs, value))
        return rows

    def total(self, **attrs: Any) -> int | float:
        """Sum the points matching ``attrs`` (exact attribute match)."""
        total: int | float = 0
        for got_attrs, value in self.points():
            if got_attrs == attrs:
                total += value
        return total


def install_counter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str,
    attr_name: str,
    modules: Iterable[str],
) -> CounterHarness:
    """Replace ``attr_name`` on each of ``modules`` with a fresh counter.

    ``name`` is the OTel metric name. ``modules`` are dotted module
    paths that imported the counter under ``attr_name`` — the metrics
    module itself MUST be included so the catalog stays consistent.
    """
    import importlib

    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    meter = provider.get_meter("app_platform")
    counter = meter.create_counter(name=name, unit="1")
    for dotted in modules:
        mod = importlib.import_module(dotted)
        monkeypatch.setattr(mod, attr_name, counter, raising=True)
    return CounterHarness(reader=reader, counter=counter, metric_name=name)
