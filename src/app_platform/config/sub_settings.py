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
    def from_app_settings(cls, app: Any) -> DatabaseSettings:
        return cls(
            dsn=app.postgresql_dsn,
            pool_size=app.db_pool_size,
            max_overflow=app.db_max_overflow,
            pool_recycle_seconds=app.db_pool_recycle_seconds,
            pool_pre_ping=app.db_pool_pre_ping,
        )

    def validate_production(self, errors: list[str]) -> None:  # noqa: ARG002
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
    def from_app_settings(cls, app: Any) -> ApiSettings:
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
    otel_traces_sampler_ratio: float
    otel_instrument_sqlalchemy: bool
    otel_instrument_httpx: bool
    otel_instrument_redis: bool
    metrics_enabled: bool
    health_ready_probe_timeout_seconds: float
    shutdown_timeout_seconds: float
    auth_redis_url: str | None
    jobs_redis_url: str | None
    environment: str

    @classmethod
    def from_app_settings(cls, app: Any) -> ObservabilitySettings:
        return cls(
            log_level=app.log_level,
            otel_exporter_endpoint=app.otel_exporter_endpoint,
            otel_service_name=app.otel_service_name,
            otel_service_version=app.otel_service_version,
            otel_traces_sampler_ratio=app.otel_traces_sampler_ratio,
            otel_instrument_sqlalchemy=app.otel_instrument_sqlalchemy,
            otel_instrument_httpx=app.otel_instrument_httpx,
            otel_instrument_redis=app.otel_instrument_redis,
            metrics_enabled=app.metrics_enabled,
            health_ready_probe_timeout_seconds=app.health_ready_probe_timeout_seconds,
            shutdown_timeout_seconds=app.shutdown_timeout_seconds,
            auth_redis_url=app.auth_redis_url,
            jobs_redis_url=app.jobs_redis_url,
            environment=app.environment,
        )

    def validate(self, errors: list[str]) -> None:
        """Validate fields that must be well-formed in every environment."""
        if not (0.0 <= self.otel_traces_sampler_ratio <= 1.0):
            errors.append(
                "APP_OTEL_TRACES_SAMPLER_RATIO must be between 0.0 and 1.0 "
                f"(got {self.otel_traces_sampler_ratio})"
            )
        # Kubelet readiness probes run on a ~10 s cadence; 30 s is already
        # generous. The lower bound is strict because a zero/negative timeout
        # would short-circuit ``asyncio.wait_for`` and report false negatives.
        _max_ready_timeout = 30.0
        if not (0.0 < self.health_ready_probe_timeout_seconds <= _max_ready_timeout):
            errors.append(
                "APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS must be in "
                f"(0.0, {_max_ready_timeout}] "
                f"(got {self.health_ready_probe_timeout_seconds})"
            )
        # ``APP_SHUTDOWN_TIMEOUT_SECONDS`` bounds the API drain budget (uvicorn's
        # ``--timeout-graceful-shutdown``) and the worker's ``on_shutdown`` wait
        # for the in-flight relay tick. Zero would short-circuit ``asyncio.wait``
        # and force-cancel in-flight work; very large values delay the K8s
        # ``terminationGracePeriodSeconds`` budget. The 300 s upper bound is
        # generous — operators with longer-running jobs should raise the K8s
        # grace period to match in addition to bumping this knob.
        _max_shutdown_timeout = 300.0
        if not (0.0 < self.shutdown_timeout_seconds <= _max_shutdown_timeout):
            errors.append(
                "APP_SHUTDOWN_TIMEOUT_SECONDS must be in "
                f"(0.0, {_max_shutdown_timeout}] "
                f"(got {self.shutdown_timeout_seconds})"
            )

    def validate_production(self, errors: list[str]) -> None:  # noqa: ARG002
        """No production-only constraints today."""
        return
