"""Cross-cutting observability primitives (logging, tracing, metrics)."""

from app_platform.observability.logging import (
    REQUEST_ID_CONTEXT,
    TRACE_ID_CONTEXT,
    RequestIdFilter,
    configure_logging,
)
from app_platform.observability.tracing import (
    configure_tracing,
    email_hash,
    instrument_fastapi_app,
    shutdown_tracing,
    traced,
)

__all__ = [
    "REQUEST_ID_CONTEXT",
    "TRACE_ID_CONTEXT",
    "RequestIdFilter",
    "configure_logging",
    "configure_tracing",
    "email_hash",
    "instrument_fastapi_app",
    "shutdown_tracing",
    "traced",
]
