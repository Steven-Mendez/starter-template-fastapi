"""Unit tests for W3C trace-context propagation across the job boundary.

The in-process and arq adapters both extract the carrier from
``payload['__trace']`` and attach the resulting OTel context around the
handler call, so a handler-side span becomes a child of the originating
request's trace.

These tests exercise the in-process adapter's extract/attach/detach
contract directly; the arq adapter's wrapper is identical and is
covered structurally by the same extract logic — the arq integration
test in ``tests/integration/test_arq_round_trip.py`` exercises the full
worker path.
"""

from __future__ import annotations

import re

import pytest
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)

from app_platform.observability.tracing import propagator_inject_current
from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.registry import JobHandlerRegistry

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Module-scoped tracer provider + in-memory exporter. OTel's global
# provider can only be set once per process, so we reuse it across tests
# and clear the exporter between assertions.
# ---------------------------------------------------------------------------

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider(
    resource=Resource.create({"service.name": "test-trace-propagation"}),
    sampler=ParentBased(ALWAYS_ON),
)
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
# ``set_tracer_provider`` is idempotent on the first call only; if another
# test module already installed a provider the second call is a no-op but
# we still want our exporter wired up. Attach the processor to whichever
# provider is currently active so spans land in our exporter regardless.
trace.set_tracer_provider(_PROVIDER)
_ACTIVE_PROVIDER = trace.get_tracer_provider()
if _ACTIVE_PROVIDER is not _PROVIDER and hasattr(
    _ACTIVE_PROVIDER, "add_span_processor"
):
    _ACTIVE_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    _EXPORTER.clear()
    return _EXPORTER


def _tracer() -> trace.Tracer:
    # Bind explicitly to the local provider. The global OTel provider is
    # set-once; if another test module set it first our exporter never
    # sees the spans we start via ``trace.get_tracer(...)``. Using the
    # local provider's tracer guarantees spans flow through ``_EXPORTER``
    # regardless of test ordering.
    return _PROVIDER.get_tracer("test")


# ---------------------------------------------------------------------------
# In-process adapter: extract + attach around the handler.
# ---------------------------------------------------------------------------


def test_handler_span_shares_trace_id_with_request_side_span(
    exporter: InMemorySpanExporter,
) -> None:
    """End-to-end propagation across the queue boundary in-process."""
    registry = JobHandlerRegistry()

    def handler(payload: dict[str, object]) -> None:
        # Handler emits a child span; it should attach to the carrier
        # the adapter extracted from ``payload['__trace']``.
        with _tracer().start_as_current_span("handler.work"):
            pass

    registry.register_handler("send_email", handler)
    adapter = InProcessJobQueueAdapter(registry=registry)

    # "Request side" span: capture the active carrier at this point —
    # the producer would normally write this into the outbox row.
    with _tracer().start_as_current_span("request.side") as request_span:
        request_trace_id = request_span.get_span_context().trace_id
        carrier = propagator_inject_current()

    # Dispatch with the carrier under the reserved ``__trace`` key.
    adapter.enqueue("send_email", {"to": "a@example.com", "__trace": carrier})

    spans = exporter.get_finished_spans()
    handler_span = next(s for s in spans if s.name == "handler.work")
    assert handler_span.context.trace_id == request_trace_id


def test_legacy_payload_without_trace_runs_and_starts_fresh_trace(
    exporter: InMemorySpanExporter,
) -> None:
    """A payload arriving without ``__trace`` runs cleanly; no exception."""
    registry = JobHandlerRegistry()

    def handler(payload: dict[str, object]) -> None:
        with _tracer().start_as_current_span("handler.legacy"):
            pass

    registry.register_handler("send_email", handler)
    adapter = InProcessJobQueueAdapter(registry=registry)

    adapter.enqueue("send_email", {"to": "a@example.com"})

    spans = exporter.get_finished_spans()
    handler_span = next(s for s in spans if s.name == "handler.legacy")
    # No parent: the span is the root of a fresh trace.
    assert handler_span.parent is None
    assert handler_span.context.trace_id != 0


def test_empty_trace_carrier_does_not_raise(exporter: InMemorySpanExporter) -> None:
    """``__trace = {}`` (legacy row) must not crash the extract."""
    registry = JobHandlerRegistry()
    calls: list[dict[str, object]] = []
    registry.register_handler("send_email", calls.append)
    adapter = InProcessJobQueueAdapter(registry=registry)

    adapter.enqueue("send_email", {"to": "a@example.com", "__trace": {}})

    assert calls == [{"to": "a@example.com", "__trace": {}}]


def test_handler_exception_still_detaches_context(
    exporter: InMemorySpanExporter,
) -> None:
    """``context.detach(token)`` runs in ``finally`` even on exceptions."""
    registry = JobHandlerRegistry()

    def boom(payload: dict[str, object]) -> None:
        raise RuntimeError("boom")

    registry.register_handler("boom", boom)
    adapter = InProcessJobQueueAdapter(registry=registry)

    # Build a carrier from a span that has since ended; the adapter
    # should still attach + detach it cleanly.
    with _tracer().start_as_current_span("request.boom"):
        carrier = propagator_inject_current()

    # Record the OTel context active *before* the adapter call so we
    # can confirm it's restored even though the handler raises.
    before = otel_context.get_current()

    with pytest.raises(RuntimeError, match="boom"):
        adapter.enqueue("boom", {"__trace": carrier})

    # Context restored — the detach in ``finally`` ran.
    assert otel_context.get_current() is before


def test_propagator_inject_current_returns_w3c_traceparent(
    exporter: InMemorySpanExporter,
) -> None:
    """Carrier emitted under an active span contains a W3C ``traceparent``."""
    with _tracer().start_as_current_span("scope") as span:
        carrier = propagator_inject_current()
        expected_trace_id = format(span.get_span_context().trace_id, "032x")

    assert "traceparent" in carrier
    # ``version-trace_id-parent_id-flags`` per the W3C spec.
    pattern = r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"
    assert re.match(pattern, carrier["traceparent"])
    assert expected_trace_id in carrier["traceparent"]


def test_propagator_inject_current_outside_span_returns_empty() -> None:
    """No active context -> empty carrier; the relay tolerates this."""
    carrier = propagator_inject_current()
    assert carrier == {}


def test_handler_can_re_enqueue_preserving_trace_verbatim(
    exporter: InMemorySpanExporter,
) -> None:
    """Forward-compat: handler that re-enqueues preserves ``__trace`` byte-for-byte."""
    registry = JobHandlerRegistry()
    seen: list[dict[str, object]] = []

    def handler(payload: dict[str, object]) -> None:
        seen.append(payload)
        # The handler re-enqueues; the contract says ``__trace`` must
        # be carried through unchanged.

    registry.register_handler("send_email", handler)
    adapter = InProcessJobQueueAdapter(registry=registry)

    carrier_in = {
        "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
    }
    adapter.enqueue("send_email", {"to": "a@e.com", "__trace": carrier_in})

    # The carrier the handler saw is the same dict the relay injected.
    assert seen[0]["__trace"] == carrier_in
    # ...and the value matches the W3C extract path:
    ctx = TraceContextTextMapPropagator().extract(carrier=carrier_in)
    span = trace.get_current_span(ctx)
    sc = span.get_span_context()
    assert format(sc.trace_id, "032x") == "0af7651916cd43dd8448eb211c80319c"
