"""OpenTelemetry meter setup and ``/metrics`` exposition.

The platform exposes a single OTel ``MeterProvider`` wired to a
:class:`PrometheusMetricReader` so the same SDK / exporter pipeline
serves both metrics and traces (see :mod:`tracing`). Features obtain
:class:`opentelemetry.metrics.Meter` instances exclusively through
:func:`get_app_meter` — they MUST NOT call
:func:`opentelemetry.metrics.get_meter` directly. This indirection
gives us one place to centralize naming conventions, sampling defaults,
and test isolation.

Naming convention: ``app_<feature>_<noun>_<unit>``.

* ``_total`` suffix on monotonic counters.
* ``_gauge`` suffix on observable gauges.
* ``_seconds`` suffix on durations.
* Label sets are closed: no user-id, no path-templated cardinality.

Initial metric catalog (one production call site each):

* ``app_auth_logins_total{result}`` — counter; ``result ∈ {success, failure}``.
* ``app_auth_refresh_total{result}`` — counter; ``result ∈ {success, failure}``.
* ``app_outbox_dispatched_total{result}`` — counter; ``result ∈ {success, failure}``.
* ``app_outbox_pending_gauge`` — observable gauge; callback bound at composition.
* ``app_jobs_enqueued_total{handler}`` — counter; ``handler`` bounded by registry.
* ``app_db_pool_checked_in`` / ``_checked_out`` / ``_overflow`` / ``_size`` —
  observable gauges; callbacks bound at composition.

Usage::

    from app_platform.observability.metrics import (
        get_app_meter,
        AUTH_LOGINS_TOTAL,
    )
    AUTH_LOGINS_TOTAL.add(1, attributes={"result": "success"})
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from opentelemetry import metrics as otel_metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import CallbackOptions, Meter, Observation
from opentelemetry.sdk.metrics import MeterProvider

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MeterProvider singleton
# ---------------------------------------------------------------------------

# Module-level singleton. The provider is built lazily on first
# :func:`get_app_meter` call (and on import via the eager declarations
# below) so tests can swap it out by calling :func:`reset_meter_provider`
# before importing modules that declare instruments.
_METER_PROVIDER: MeterProvider | None = None
_PROMETHEUS_READER: PrometheusMetricReader | None = None


def _build_meter_provider() -> tuple[MeterProvider, PrometheusMetricReader]:
    """Construct a ``MeterProvider`` wired to a ``PrometheusMetricReader``.

    The reader registers itself against ``prometheus_client.REGISTRY``
    so :func:`prometheus_client.make_asgi_app` exposes everything the
    OTel SDK produces. Kept package-private; tests use
    :func:`reset_meter_provider` instead.
    """
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return provider, reader


def _ensure_provider() -> MeterProvider:
    """Return the process-wide ``MeterProvider``, building it on demand."""
    global _METER_PROVIDER, _PROMETHEUS_READER
    if _METER_PROVIDER is None:
        _METER_PROVIDER, _PROMETHEUS_READER = _build_meter_provider()
        otel_metrics.set_meter_provider(_METER_PROVIDER)
    return _METER_PROVIDER


def reset_meter_provider() -> None:
    """Reset the singleton (test-only).

    Drops the cached provider and reader so the next :func:`get_app_meter`
    call rebuilds them. Production code should never call this; tests
    that need a fresh SDK between cases do.
    """
    global _METER_PROVIDER, _PROMETHEUS_READER  # noqa: PLW0603
    _METER_PROVIDER = None
    _PROMETHEUS_READER = None


def get_app_meter(feature: str) -> Meter:
    """Return a :class:`Meter` scoped to ``feature``.

    Features call this from their composition or application layer
    instead of :func:`opentelemetry.metrics.get_meter` so the platform
    owns naming, SDK selection, and test isolation. The ``feature``
    string is used as the meter's instrumentation-scope name (e.g.
    ``"authentication"``, ``"outbox"``).
    """
    provider = _ensure_provider()
    return provider.get_meter(feature)


# ---------------------------------------------------------------------------
# Initial metric catalog
# ---------------------------------------------------------------------------
#
# Instruments are declared at import time against the platform meter so
# call sites can ``from app_platform.observability.metrics import
# AUTH_LOGINS_TOTAL`` and increment without re-discovering the meter.
# Observable gauges have their callbacks bound separately by
# :func:`register_outbox_pending_callback` / :func:`register_db_pool_gauges`
# in :mod:`main` once the engine exists.

_PLATFORM_METER: Meter = get_app_meter("app_platform")

AUTH_LOGINS_TOTAL = _PLATFORM_METER.create_counter(
    name="app_auth_logins_total",
    description="Total login attempts, labelled by outcome (success / failure).",
    unit="1",
)

AUTH_REFRESH_TOTAL = _PLATFORM_METER.create_counter(
    name="app_auth_refresh_total",
    description="Total refresh-token rotations, labelled by outcome.",
    unit="1",
)

OUTBOX_DISPATCHED_TOTAL = _PLATFORM_METER.create_counter(
    name="app_outbox_dispatched_total",
    description="Total outbox rows dispatched, labelled by outcome.",
    unit="1",
)

JOBS_ENQUEUED_TOTAL = _PLATFORM_METER.create_counter(
    name="app_jobs_enqueued_total",
    description="Total background jobs enqueued, labelled by handler name.",
    unit="1",
)


# ---------------------------------------------------------------------------
# Observable gauges (callbacks bound at composition time)
# ---------------------------------------------------------------------------
#
# Observable instruments are stored module-level so composition can
# register callbacks once the engine / connection is known. The
# callback list is mutated, never re-bound, so the OTel SDK keeps its
# reference to the original callables. Each registration helper is
# idempotent at the SDK level: re-registering is a no-op because we
# build the gauge exactly once and append callbacks to its list.

_outbox_pending_callbacks: list[Callable[[CallbackOptions], Iterable[Observation]]] = []
_db_pool_checked_in_callbacks: list[
    Callable[[CallbackOptions], Iterable[Observation]]
] = []
_db_pool_checked_out_callbacks: list[
    Callable[[CallbackOptions], Iterable[Observation]]
] = []
_db_pool_overflow_callbacks: list[
    Callable[[CallbackOptions], Iterable[Observation]]
] = []
_db_pool_size_callbacks: list[Callable[[CallbackOptions], Iterable[Observation]]] = []


def _outbox_pending_dispatch(options: CallbackOptions) -> Iterable[Observation]:
    for cb in _outbox_pending_callbacks:
        yield from cb(options)


def _db_pool_checked_in_dispatch(options: CallbackOptions) -> Iterable[Observation]:
    for cb in _db_pool_checked_in_callbacks:
        yield from cb(options)


def _db_pool_checked_out_dispatch(options: CallbackOptions) -> Iterable[Observation]:
    for cb in _db_pool_checked_out_callbacks:
        yield from cb(options)


def _db_pool_overflow_dispatch(options: CallbackOptions) -> Iterable[Observation]:
    for cb in _db_pool_overflow_callbacks:
        yield from cb(options)


def _db_pool_size_dispatch(options: CallbackOptions) -> Iterable[Observation]:
    for cb in _db_pool_size_callbacks:
        yield from cb(options)


# Declare the gauges eagerly so they appear in ``/metrics`` even before
# composition wires the callbacks (they simply yield nothing until then,
# which is the same shape as a zero-callback observable gauge).
OUTBOX_PENDING_GAUGE = _PLATFORM_METER.create_observable_gauge(
    name="app_outbox_pending_gauge",
    description="Outbox rows in status='pending' at scrape time.",
    unit="1",
    callbacks=[_outbox_pending_dispatch],
)

DB_POOL_CHECKED_IN = _PLATFORM_METER.create_observable_gauge(
    name="app_db_pool_checked_in",
    description="SQLAlchemy pool: connections currently checked in (idle).",
    unit="1",
    callbacks=[_db_pool_checked_in_dispatch],
)

DB_POOL_CHECKED_OUT = _PLATFORM_METER.create_observable_gauge(
    name="app_db_pool_checked_out",
    description="SQLAlchemy pool: connections currently checked out (in use).",
    unit="1",
    callbacks=[_db_pool_checked_out_dispatch],
)

DB_POOL_OVERFLOW = _PLATFORM_METER.create_observable_gauge(
    name="app_db_pool_overflow",
    description="SQLAlchemy pool: current overflow above the pool size.",
    unit="1",
    callbacks=[_db_pool_overflow_dispatch],
)

DB_POOL_SIZE = _PLATFORM_METER.create_observable_gauge(
    name="app_db_pool_size",
    description="SQLAlchemy pool: configured pool size.",
    unit="1",
    callbacks=[_db_pool_size_dispatch],
)


# ---------------------------------------------------------------------------
# Composition-time callback registration
# ---------------------------------------------------------------------------


def register_outbox_pending_callback(engine: Engine) -> None:
    """Bind the ``app_outbox_pending_gauge`` callback to ``engine``.

    Runs ``SELECT COUNT(*) FROM outbox_messages WHERE status='pending'``
    on every scrape, guarded by ``SET LOCAL statement_timeout='2s'`` so a
    slow database cannot stall the Prometheus scrape path. The callback
    swallows query failures and returns an empty observation (operator
    sees the gauge drop out of ``/metrics`` rather than a 500 from the
    scrape endpoint).

    Composition calls this once after the engine is built; calling it a
    second time appends a second callback (no-op for tests that mutate
    the same engine).
    """
    from sqlalchemy import text

    def _callback(_: CallbackOptions) -> Iterable[Observation]:
        try:
            with engine.connect() as conn:
                if engine.dialect.name == "postgresql":
                    conn.execute(text("SET LOCAL statement_timeout = '2s'"))
                count = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM outbox_messages WHERE status = 'pending'"
                    )
                ).scalar_one()
        except Exception:
            _logger.warning("event=metrics.outbox_pending.query_failed", exc_info=True)
            return ()
        return (Observation(int(count)),)

    _outbox_pending_callbacks.append(_callback)


def register_db_pool_gauges(engine: Engine) -> None:
    """Bind the four ``app_db_pool_*`` callbacks to ``engine``.

    Reads :class:`sqlalchemy.pool.QueuePool` accessors (``checkedin``,
    ``checkedout``, ``overflow``, ``size``). These are constant-time
    in-memory counters on the pool object; no DB roundtrip per scrape.

    For pools that lack one of the accessors (e.g. ``SingletonThreadPool``
    used by the SQLite test rig has only ``size``), the missing accessor
    yields nothing rather than raising.
    """

    def _safe(method_name: str) -> Callable[[CallbackOptions], Iterable[Observation]]:
        def _callback(_: CallbackOptions) -> Iterable[Observation]:
            pool: Any = engine.pool
            fn = getattr(pool, method_name, None)
            if fn is None:
                return ()
            try:
                value = fn()
            except Exception:
                _logger.warning(
                    "event=metrics.db_pool.read_failed method=%s",
                    method_name,
                    exc_info=True,
                )
                return ()
            return (Observation(int(value)),)

        return _callback

    _db_pool_checked_in_callbacks.append(_safe("checkedin"))
    _db_pool_checked_out_callbacks.append(_safe("checkedout"))
    _db_pool_overflow_callbacks.append(_safe("overflow"))
    _db_pool_size_callbacks.append(_safe("size"))


# ---------------------------------------------------------------------------
# /metrics ASGI mount
# ---------------------------------------------------------------------------


def configure_metrics(app: object, *, enabled: bool = True) -> None:
    """Mount ``/metrics`` on ``app`` backed by the OTel Prometheus reader.

    The :class:`PrometheusMetricReader` registers itself against
    ``prometheus_client.REGISTRY``, so
    :func:`prometheus_client.make_asgi_app` exports everything the
    OTel SDK produces. We replace the legacy
    ``prometheus_fastapi_instrumentator`` mount with this thin ASGI
    sub-app — RED metrics (HTTP duration / errors / rate) are owned by
    the FastAPI auto-instrumentation in :mod:`tracing` / the
    metric-side OTel instrumentation in subsequent changes.

    When ``enabled`` is ``False`` the provider is still constructed
    (so feature imports of counters remain valid in tests) but the
    endpoint is not mounted.
    """
    from fastapi import FastAPI
    from prometheus_client import make_asgi_app

    if not isinstance(app, FastAPI):
        return

    # Make sure the provider — and therefore the Prometheus reader —
    # is built before the ASGI app starts serving scrapes.
    _ensure_provider()

    if enabled:
        app.mount("/metrics", make_asgi_app(), name="metrics")
        _logger.info("event=metrics.enabled endpoint=/metrics")
    else:
        _logger.info(
            "event=metrics.disabled "
            "message=Set APP_METRICS_ENABLED=true to expose /metrics"
        )


__all__ = [
    "AUTH_LOGINS_TOTAL",
    "AUTH_REFRESH_TOTAL",
    "DB_POOL_CHECKED_IN",
    "DB_POOL_CHECKED_OUT",
    "DB_POOL_OVERFLOW",
    "DB_POOL_SIZE",
    "JOBS_ENQUEUED_TOTAL",
    "OUTBOX_DISPATCHED_TOTAL",
    "OUTBOX_PENDING_GAUGE",
    "configure_metrics",
    "get_app_meter",
    "register_db_pool_gauges",
    "register_outbox_pending_callback",
    "reset_meter_provider",
]
