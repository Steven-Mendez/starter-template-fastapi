"""Tests for ``configure_tracing`` setup branches.

These tests patch the instrumentor classes so the real OTel exporter and
network sockets are not invoked. They assert which instrumentors are
called based on the settings toggles.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

import app_platform.observability.tracing as tracing_module
from app_platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_tracing_state() -> Any:
    """Ensure each test starts with no global provider configured."""
    tracing_module._TRACING_CONFIGURED = False
    tracing_module._PROVIDER = None
    yield
    tracing_module._TRACING_CONFIGURED = False
    tracing_module._PROVIDER = None


def _settings(**overrides: Any) -> AppSettings:
    base: dict[str, Any] = {
        "environment": "test",
        "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
        "otel_exporter_endpoint": "http://localhost:4318/v1/traces",
    }
    base.update(overrides)
    return AppSettings(**base)


def test_redis_instrumentor_skipped_when_no_redis_url() -> None:
    settings = _settings(auth_redis_url=None)

    with patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as redis_cls:
        tracing_module.configure_tracing(settings)
        redis_cls.assert_not_called()


def test_redis_instrumentor_skipped_when_toggle_off() -> None:
    settings = _settings(
        auth_redis_url="redis://localhost:6379",
        otel_instrument_redis=False,
    )
    with patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as redis_cls:
        tracing_module.configure_tracing(settings)
        redis_cls.assert_not_called()


def test_httpx_instrumentor_skipped_when_toggle_off() -> None:
    settings = _settings(otel_instrument_httpx=False)
    with patch(
        "opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor"
    ) as httpx_cls:
        tracing_module.configure_tracing(settings)
        httpx_cls.assert_not_called()


def test_sqlalchemy_instrumentor_skipped_when_toggle_off() -> None:
    settings = _settings(otel_instrument_sqlalchemy=False)
    with patch(
        "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
    ) as sa_cls:
        tracing_module.configure_tracing(settings)
        sa_cls.assert_not_called()


def test_redis_instrumentor_runs_when_auth_redis_url_set() -> None:
    # ``jobs_redis_url`` was removed with the arq adapter (ROADMAP ETAPA
    # I step 5); ``auth_redis_url`` is now the only Redis URL signal the
    # tracing setup reads (the auth rate limiter / principal cache).
    settings = _settings(auth_redis_url="redis://localhost:6379")
    with patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as redis_cls:
        tracing_module.configure_tracing(settings)
        redis_cls.assert_called_once()


def test_production_ratio_one_emits_warning(caplog: pytest.LogCaptureFixture) -> None:
    # NOTE: after ROADMAP ETAPA I step 4 (Resend removed, AWS SES not yet
    # added) there is no production-capable email backend — the only
    # value, ``console``, is refused by the production validator. A
    # *validated* production ``AppSettings`` is therefore not constructible
    # until AWS SES lands. This test asserts a tracing-warning branch, not
    # a boot, so it builds the instance via ``model_construct`` (skipping
    # the production validator) with exactly the attributes
    # ``configure_tracing`` reads. ``email_backend="console"`` is set per
    # the change spec; the production validator is deliberately not the
    # path under test here.
    settings = AppSettings.model_construct(
        environment="production",
        email_backend="console",
        email_from="noreply@example.com",
        otel_exporter_endpoint="http://collector:4318/v1/traces",
        otel_traces_sampler_ratio=1.0,
        otel_service_name="starter-template-fastapi",
        otel_service_version="0.1.0",
        otel_instrument_sqlalchemy=False,
        otel_instrument_httpx=False,
        otel_instrument_redis=False,
        auth_redis_url=None,
    )

    with caplog.at_level("WARNING", logger="app_platform.observability.tracing"):
        tracing_module.configure_tracing(settings)

    assert any(
        "otel.tracing.sampler.high_ratio" in record.getMessage()
        for record in caplog.records
    )


def test_shutdown_tracing_is_idempotent() -> None:
    # Never configured: no-op.
    tracing_module.shutdown_tracing()

    settings = _settings()
    tracing_module.configure_tracing(settings)
    assert tracing_module._PROVIDER is not None

    tracing_module.shutdown_tracing()
    assert tracing_module._PROVIDER is None

    # Second call is also a no-op.
    tracing_module.shutdown_tracing()


def test_invalid_sampler_ratio_refuses_startup() -> None:
    with pytest.raises(ValueError, match="OTEL_TRACES_SAMPLER_RATIO"):
        AppSettings(
            environment="test",
            auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
            otel_traces_sampler_ratio=1.5,
        )
