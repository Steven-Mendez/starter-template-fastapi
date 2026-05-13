"""OpenTelemetry tracing setup.

Tracing is opt-in: set ``APP_OTEL_EXPORTER_ENDPOINT`` to enable it. When the
endpoint is not configured this module does not install instrumentation, leaving
OpenTelemetry's default no-op provider in place for development and tests.

Exported spans are sent over HTTP OTLP to the configured endpoint so no
gRPC dependency is required. Compatible with Jaeger, Tempo, the OTel
Collector, and any OTLP-capable backend.

Usage (add once at process startup, before routes are called)::

    from app_platform.observability.tracing import configure_tracing
    configure_tracing(settings)

The :func:`traced` decorator wraps any sync or async callable in a span with
the supplied ``name`` and ``attrs``. It records exceptions and re-raises;
callers always observe the original exception.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable, Mapping
from typing import Any, TypeVar, cast

from fastapi import FastAPI

F = TypeVar("F", bound=Callable[..., Any])

# ``AppSettings`` is not imported here on purpose: tracing is an inner
# platform module and pulling in ``app_platform.config.settings`` would
# transitively reference every feature's composition.settings, which
# Import Linter forbids for cross-feature isolation contracts (e.g. the
# outbox feature's). ``configure_tracing`` and ``instrument_fastapi_app``
# accept ``AppSettings`` structurally — the only attributes they read
# are documented in the parameter docstrings.

_logger = logging.getLogger(__name__)
_TRACING_CONFIGURED = False
_PROVIDER: Any | None = None

_EXCLUDED_FASTAPI_URLS = ",".join(
    (
        "/health/live",
        "/health/ready",
        "/health",
        "/metrics",
    )
)


def configure_tracing(settings: Any) -> None:
    """Set up the global tracer provider.

    When ``otel_exporter_endpoint`` is configured, spans are exported via
    OTLP/HTTP. Otherwise no provider or instrumentation is installed.

    SQLAlchemy, HTTPX, and Redis auto-instrumentations are each gated by a
    settings toggle (default ``true``). Redis is additionally skipped when
    no Redis URL is configured. FastAPI apps are instrumented with
    :func:`instrument_fastapi_app` once the app object exists.

    A startup warning (NOT a refusal) is emitted when the environment is
    ``production`` and the sampler ratio is ``1.0``: production operators
    almost always want to sample below 100%, but enforcing a refusal would
    deny perfectly reasonable bootstrap configurations. This is the only
    "warn but don't refuse" path in the codebase.
    """
    global _TRACING_CONFIGURED, _PROVIDER  # noqa: PLW0603 — module-level singleton

    if not settings.otel_exporter_endpoint:
        _logger.info(
            "event=otel.tracing.disabled "
            "message=Set APP_OTEL_EXPORTER_ENDPOINT to enable span export"
        )
        return

    if _TRACING_CONFIGURED:
        return

    if (
        settings.environment == "production"
        and settings.otel_traces_sampler_ratio == 1.0
    ):
        _logger.warning(
            "event=otel.tracing.sampler.high_ratio "
            "ratio=1.0 environment=production "
            "message=APP_OTEL_TRACES_SAMPLER_RATIO=1.0 in production will "
            "flood the collector under load; recommend a value below 1.0 "
            "(e.g. 0.1). This is a warning, not a refusal."
        )

    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    resource = Resource.create(
        {
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_VERSION: settings.otel_service_version,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(settings.otel_traces_sampler_ratio)),
    )

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )

    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
    # Bumped from the OTel SDK defaults (max_queue=2048, batch=512) so bursty
    # traffic does not silently drop spans before the collector catches up.
    provider.add_span_processor(
        BatchSpanProcessor(
            exporter,
            max_queue_size=8192,
            max_export_batch_size=512,
        )
    )
    _logger.info(
        "event=otel.tracing.enabled endpoint=%s sampler_ratio=%s",
        settings.otel_exporter_endpoint,
        settings.otel_traces_sampler_ratio,
    )

    trace.set_tracer_provider(provider)

    if settings.otel_instrument_sqlalchemy:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument()

    if settings.otel_instrument_httpx:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()

    if settings.otel_instrument_redis and (
        settings.auth_redis_url or settings.jobs_redis_url
    ):
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()

    _PROVIDER = provider
    _TRACING_CONFIGURED = True


def shutdown_tracing() -> None:
    """Idempotently flush and shut down the global tracer provider.

    Safe to call multiple times and safe to call when tracing was never
    configured (no-op in both cases). Intended for the FastAPI lifespan
    finalizer and the worker's graceful-shutdown path.
    """
    global _TRACING_CONFIGURED, _PROVIDER  # noqa: PLW0603

    if _PROVIDER is None:
        return
    try:
        _PROVIDER.shutdown()
    except Exception:  # pragma: no cover — defensive; shutdown is best-effort
        _logger.exception("event=otel.tracing.shutdown.failed")
    finally:
        _PROVIDER = None
        _TRACING_CONFIGURED = False


def instrument_fastapi_app(app: FastAPI, settings: Any) -> None:
    """Instrument one FastAPI app instance when tracing is enabled."""
    if not settings.otel_exporter_endpoint:
        return
    if getattr(app.state, "otel_instrumented", False):
        return

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=_EXCLUDED_FASTAPI_URLS,
    )
    app.state.otel_instrumented = True


# ---------------------------------------------------------------------------
# @traced decorator
# ---------------------------------------------------------------------------

AttrsArg = Mapping[str, Any] | Callable[..., Mapping[str, Any]] | None


def _resolve_attrs(
    attrs: AttrsArg,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Mapping[str, Any]:
    if attrs is None:
        return {}
    if callable(attrs):
        try:
            return attrs(*args, **kwargs)
        except Exception:
            _logger.exception("event=otel.traced.attrs.callable_failed")
            return {}
    return attrs


def _apply_span_attrs(span: Any, attrs: Mapping[str, Any]) -> None:
    for key, value in attrs.items():
        if value is None:
            continue
        # OTel only accepts primitive types and sequences of primitives.
        if isinstance(value, str | bool | int | float):
            span.set_attribute(key, value)
        else:
            span.set_attribute(key, str(value))


def traced(
    name: str,
    *,
    attrs: AttrsArg = None,
) -> Callable[[F], F]:
    """Wrap a callable in an OTel span named ``name``.

    ``attrs`` may be a static dict or a callable receiving the wrapped
    function's positional/keyword arguments and returning a dict. Values
    that are ``None`` are dropped; non-primitive values are stringified.

    On raised exception the decorator records the exception on the span,
    flips the span status to ``ERROR``, and re-raises so the caller sees
    the original exception unchanged.

    The decorator detects coroutine functions and returns the appropriate
    sync or async wrapper.
    """

    def _decorator(func: F) -> F:
        is_async = asyncio.iscoroutinefunction(func) or inspect.iscoroutinefunction(
            func
        )

        if is_async:

            @functools.wraps(func)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                from opentelemetry import trace
                from opentelemetry.trace import StatusCode

                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span(name) as span:
                    resolved = _resolve_attrs(attrs, args, kwargs)
                    _apply_span_attrs(span, resolved)
                    try:
                        return await func(*args, **kwargs)
                    except BaseException as exc:
                        span.record_exception(exc)
                        span.set_status(StatusCode.ERROR, str(exc))
                        raise

            return cast(F, _async_wrapper)

        @functools.wraps(func)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            from opentelemetry import trace
            from opentelemetry.trace import StatusCode

            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(name) as span:
                resolved = _resolve_attrs(attrs, args, kwargs)
                _apply_span_attrs(span, resolved)
                try:
                    return func(*args, **kwargs)
                except BaseException as exc:
                    span.record_exception(exc)
                    span.set_status(StatusCode.ERROR, str(exc))
                    raise

        return cast(F, _sync_wrapper)

    return _decorator


def email_hash(email: str) -> str:
    """Return a deterministic short hash of ``email`` for span attributes.

    Raw email addresses MUST NOT appear in span attributes (PII). Use this
    helper to derive a stable identifier for cross-trace correlation.
    """
    import hashlib

    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]
