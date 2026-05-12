"""Platform-level typed projections over :class:`AppSettings`.

Each sub-settings class is a small immutable view that exposes the
cross-cutting platform knobs (database pool, API surface, observability)
in a structured shape. They mirror the per-feature settings classes
that live under each ``src/features/<feature>/composition/settings.py``
so the eventual decomposition has a consistent vocabulary.

The flat ``APP_*`` env vars remain the public contract; these projections
are constructed from :class:`AppSettings` and are the preferred way for
new code to read configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """PostgreSQL DSN and connection-pool tuning."""

    dsn: str
    pool_size: int
    max_overflow: int
    pool_recycle_seconds: int
    pool_pre_ping: bool

    @classmethod
    def from_app_settings(cls, app: Any) -> "DatabaseSettings":
        return cls(
            dsn=app.postgresql_dsn,
            pool_size=app.db_pool_size,
            max_overflow=app.db_max_overflow,
            pool_recycle_seconds=app.db_pool_recycle_seconds,
            pool_pre_ping=app.db_pool_pre_ping,
        )

    def validate_production(self, errors: list[str]) -> None:
        """No production-only constraints today."""
        return


@dataclass(frozen=True, slots=True)
class ApiSettings:
    """CORS, trusted hosts, docs, body-size — everything HTTP-shaped."""

    enable_docs: bool
    cors_origins: list[str]
    trusted_hosts: list[str]
    max_request_bytes: int
    public_url: str
    display_name: str

    @classmethod
    def from_app_settings(cls, app: Any) -> "ApiSettings":
        return cls(
            enable_docs=app.enable_docs,
            cors_origins=list(app.cors_origins),
            trusted_hosts=list(app.trusted_hosts),
            max_request_bytes=app.max_request_bytes,
            public_url=app.app_public_url,
            display_name=app.app_display_name,
        )

    def validate_production(self, errors: list[str]) -> None:
        if self.cors_origins == ["*"] or "*" in self.cors_origins:
            errors.append(
                "APP_CORS_ORIGINS must not be ['*'] in production; "
                "provide explicit allowed origins"
            )
        if self.enable_docs:
            errors.append("APP_ENABLE_DOCS must be False in production")


@dataclass(frozen=True, slots=True)
class ObservabilitySettings:
    """Logging, OTEL tracing, and Prometheus metrics knobs."""

    log_level: str
    otel_exporter_endpoint: str | None
    otel_service_name: str
    otel_service_version: str
    metrics_enabled: bool

    @classmethod
    def from_app_settings(cls, app: Any) -> "ObservabilitySettings":
        return cls(
            log_level=app.log_level,
            otel_exporter_endpoint=app.otel_exporter_endpoint,
            otel_service_name=app.otel_service_name,
            otel_service_version=app.otel_service_version,
            metrics_enabled=app.metrics_enabled,
        )

    def validate_production(self, errors: list[str]) -> None:
        """No production-only constraints today."""
        return
