"""Unit tests for the OpenTelemetry tracing seam.

OTel's global tracer provider may only be set once per process, so all
tests in this module share a single ``TracerProvider`` configured at
module-import time. A module-scoped ``InMemorySpanExporter`` is attached
via ``SimpleSpanProcessor`` and cleared between tests.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    SamplingResult,
)
from opentelemetry.trace import StatusCode

from app_platform.observability.tracing import email_hash, traced

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Shared in-memory provider — set once for the whole module.
# ---------------------------------------------------------------------------


class _SwappableSampler(Sampler):
    """Sampler whose delegate can be swapped per-test."""

    delegate: Sampler = ParentBased(ALWAYS_ON)

    def should_sample(  # type: ignore[no-untyped-def]
        self,
        parent_context,
        trace_id,
        name,
        kind=None,
        attributes=None,
        links=None,
        trace_state=None,
    ) -> SamplingResult:
        return self.delegate.should_sample(
            parent_context,
            trace_id,
            name,
            kind,
            attributes,
            links,
            trace_state,
        )

    def get_description(self) -> str:
        return f"SwappableSampler({self.delegate.get_description()})"


_SAMPLER = _SwappableSampler()
_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider(
    resource=Resource.create({"service.name": "test"}),
    sampler=_SAMPLER,
)
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    """Reset spans and restore default sampler before each test."""
    _EXPORTER.clear()
    _SAMPLER.delegate = ParentBased(ALWAYS_ON)
    return _EXPORTER


def test_decorator_emits_named_span(exporter: InMemorySpanExporter) -> None:
    @traced("my.span", attrs={"k": "v"})
    def fn(x: int) -> int:
        return x * 2

    assert fn(3) == 6
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "my.span"
    assert spans[0].attributes is not None
    assert spans[0].attributes["k"] == "v"


def test_decorator_with_callable_attrs(exporter: InMemorySpanExporter) -> None:
    @traced("my.span", attrs=lambda x: {"x.value": x})
    def fn(x: int) -> int:
        return x

    fn(42)
    spans = exporter.get_finished_spans()
    assert spans[0].attributes is not None
    assert spans[0].attributes["x.value"] == 42


def test_decorator_records_exception_and_reraises(
    exporter: InMemorySpanExporter,
) -> None:
    @traced("boom")
    def fn() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        fn()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert any(event.name == "exception" for event in span.events)


async def test_decorator_supports_async(exporter: InMemorySpanExporter) -> None:
    @traced("async.span")
    async def fn() -> str:
        return "ok"

    result = await fn()
    assert result == "ok"
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "async.span"


def test_decorator_drops_none_attrs(exporter: InMemorySpanExporter) -> None:
    @traced("my.span", attrs={"a": "set", "b": None})
    def fn() -> None:
        return None

    fn()
    span = exporter.get_finished_spans()[0]
    assert span.attributes is not None
    assert span.attributes.get("a") == "set"
    assert "b" not in span.attributes


def test_email_hash_is_deterministic_and_short() -> None:
    h = email_hash("alice@example.com")
    assert h == email_hash("alice@example.com")
    assert h == email_hash("ALICE@example.com")  # case-insensitive
    assert len(h) == 16
    assert "alice" not in h
    assert "example" not in h


# ---------------------------------------------------------------------------
# Sampler behaviour
# ---------------------------------------------------------------------------


def test_sampler_ratio_zero_drops_root_spans(
    exporter: InMemorySpanExporter,
) -> None:
    """With AlwaysOff (== ratio 0.0), no spans are recorded."""
    _SAMPLER.delegate = ParentBased(ALWAYS_OFF)

    @traced("dropped.span")
    def fn() -> None:
        return None

    for _ in range(5):
        fn()
    assert exporter.get_finished_spans() == ()


def test_sampler_ratio_one_keeps_all_spans(
    exporter: InMemorySpanExporter,
) -> None:
    """ALWAYS_ON keeps every root span."""
    _SAMPLER.delegate = ParentBased(ALWAYS_ON)

    @traced("kept.span")
    def fn() -> None:
        return None

    for _ in range(5):
        fn()
    assert len(exporter.get_finished_spans()) == 5
