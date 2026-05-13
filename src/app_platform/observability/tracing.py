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
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app_platform.config.settings import AppSettings

_logger = logging.getLogger(__name__)
_TRACING_CONFIGURED = False

_EXCLUDED_FASTAPI_URLS = ",".join(
    (
        "/health/live",
        "/health/ready",
        "/health",
        "/metrics",
    )
)


def configure_tracing(settings: AppSettings) -> None:
    """Set up the global tracer provider.

    When ``otel_exporter_endpoint`` is configured, spans are exported via
    OTLP/HTTP. Otherwise no provider or instrumentation is installed.

    SQLAlchemy is auto-instrumented at process level. Redis instrumentation is
    applied when ``auth_redis_url`` is set. FastAPI apps are instrumented with
    :func:`instrument_fastapi_app` once the app object exists.
    """
    global _TRACING_CONFIGURED  # noqa: PLW0603 — module-level singleton guard

    if not settings.otel_exporter_endpoint:
        _logger.info(
            "event=otel.tracing.disabled "
            "message=Set APP_OTEL_EXPORTER_ENDPOINT to enable span export"
        )
        return

    if _TRACING_CONFIGURED:
        return

    from opentelemetry import trace
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_VERSION: settings.otel_service_version,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )

    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    _logger.info(
        "event=otel.tracing.enabled endpoint=%s",
        settings.otel_exporter_endpoint,
    )

    trace.set_tracer_provider(provider)
    SQLAlchemyInstrumentor().instrument()

    if settings.auth_redis_url:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()

    _TRACING_CONFIGURED = True


def instrument_fastapi_app(app: FastAPI, settings: AppSettings) -> None:
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
