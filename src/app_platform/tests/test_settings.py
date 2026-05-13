"""Unit tests for :class:`AppSettings` defaults, env overrides, and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app_platform.config.settings import AppSettings, get_settings

pytestmark = pytest.mark.unit

_VALID_PROD_ENV = {
    "APP_ENVIRONMENT": "production",
    "APP_ENABLE_DOCS": "false",
    "APP_AUTH_JWT_SECRET_KEY": "a-secret-at-least-32-chars-long!!",
    "APP_AUTH_JWT_ISSUER": "https://issuer.example.com",
    "APP_AUTH_JWT_AUDIENCE": "starter-template-fastapi",
    "APP_CORS_ORIGINS": '["https://example.com"]',
    "APP_AUTH_COOKIE_SECURE": "true",
    "APP_EMAIL_BACKEND": "smtp",
    "APP_EMAIL_SMTP_HOST": "smtp.example.com",
    "APP_EMAIL_FROM": "no-reply@example.com",
    "APP_JOBS_BACKEND": "arq",
    "APP_JOBS_REDIS_URL": "redis://localhost:6379/0",
    "APP_OUTBOX_ENABLED": "true",
}


def test_defaults_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "APP_ENVIRONMENT",
        "APP_ENABLE_DOCS",
        "APP_CORS_ORIGINS",
        "APP_TRUSTED_HOSTS",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "development"
    assert s.enable_docs is True
    assert s.cors_origins == ["*"]


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "production"
    assert s.enable_docs is False
    assert s.auth_jwt_secret_key == "a-secret-at-least-32-chars-long!!"
    assert s.auth_cookie_secure is True


def test_invalid_environment_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_cors_origins_parsed_as_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", '["https://a.example", "https://b.example"]')
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.cors_origins == ["https://a.example", "https://b.example"]


def test_get_settings_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    get_settings.cache_clear()


def test_production_requires_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("APP_AUTH_JWT_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_SECRET_KEY"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_requires_jwt_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("APP_AUTH_JWT_ISSUER", raising=False)
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_ISSUER"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_requires_jwt_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("APP_AUTH_JWT_AUDIENCE", raising=False)
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_AUDIENCE"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_wildcard_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_CORS_ORIGINS", '["*"]')
    with pytest.raises(ValidationError, match="APP_CORS_ORIGINS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_insecure_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_COOKIE_SECURE", "false")
    with pytest.raises(ValidationError, match="APP_AUTH_COOKIE_SECURE"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_enabled_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_ENABLE_DOCS", "true")
    with pytest.raises(ValidationError, match="APP_ENABLE_DOCS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_invalid_jwt_algorithm_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_AUTH_JWT_ALGORITHM", "none")
    with pytest.raises(ValidationError, match="APP_AUTH_JWT_ALGORITHM"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_raw_wildcard_cors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_CORS_ORIGINS", '["*"]')
    with pytest.raises(ValidationError, match="APP_CORS_ORIGINS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_console_email(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_EMAIL_BACKEND", "console")
    with pytest.raises(ValidationError, match="APP_EMAIL_BACKEND"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_return_internal_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_AUTH_RETURN_INTERNAL_TOKENS", "true")
    with pytest.raises(ValidationError, match="APP_AUTH_RETURN_INTERNAL_TOKENS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_rejects_in_process_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_JOBS_BACKEND", "in_process")
    monkeypatch.delenv("APP_JOBS_REDIS_URL", raising=False)
    with pytest.raises(ValidationError, match="APP_JOBS_BACKEND"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_arq_backend_requires_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_JOBS_BACKEND", "arq")
    monkeypatch.delenv("APP_JOBS_REDIS_URL", raising=False)
    monkeypatch.delenv("APP_AUTH_REDIS_URL", raising=False)
    with pytest.raises(ValidationError, match="APP_JOBS_REDIS_URL"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_smtp_backend_requires_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_EMAIL_BACKEND", "smtp")
    monkeypatch.setenv("APP_EMAIL_FROM", "no-reply@example.com")
    monkeypatch.delenv("APP_EMAIL_SMTP_HOST", raising=False)
    with pytest.raises(ValidationError, match="APP_EMAIL_SMTP_HOST"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_smtp_backend_requires_from(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_EMAIL_BACKEND", "smtp")
    monkeypatch.setenv("APP_EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.delenv("APP_EMAIL_FROM", raising=False)
    with pytest.raises(ValidationError, match="APP_EMAIL_FROM"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_resend_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_EMAIL_BACKEND", "resend")
    monkeypatch.setenv("APP_EMAIL_FROM", "no-reply@example.com")
    monkeypatch.delenv("APP_EMAIL_RESEND_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="APP_EMAIL_RESEND_API_KEY"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_resend_backend_requires_from(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_EMAIL_BACKEND", "resend")
    monkeypatch.setenv("APP_EMAIL_RESEND_API_KEY", "re_test_key")
    monkeypatch.delenv("APP_EMAIL_FROM", raising=False)
    with pytest.raises(ValidationError, match="APP_EMAIL_FROM"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_accepts_resend_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_EMAIL_BACKEND", "resend")
    monkeypatch.setenv("APP_EMAIL_RESEND_API_KEY", "re_test_key")
    # Configured production values still satisfy SMTP fields, but Resend
    # only needs FROM + key — construct should succeed without raising.
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.email_backend == "resend"


def test_production_rejects_disabled_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_OUTBOX_ENABLED", "false")
    with pytest.raises(ValidationError, match="APP_OUTBOX_ENABLED"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_production_accepts_enabled_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _VALID_PROD_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_OUTBOX_ENABLED", "true")
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.outbox_enabled is True


def test_outbox_relay_interval_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_OUTBOX_RELAY_INTERVAL_SECONDS", "0")
    with pytest.raises(ValidationError, match="APP_OUTBOX_RELAY_INTERVAL_SECONDS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_outbox_claim_batch_size_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_OUTBOX_CLAIM_BATCH_SIZE", "0")
    with pytest.raises(ValidationError, match="APP_OUTBOX_CLAIM_BATCH_SIZE"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]


def test_outbox_max_attempts_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_OUTBOX_MAX_ATTEMPTS", "0")
    with pytest.raises(ValidationError, match="APP_OUTBOX_MAX_ATTEMPTS"):
        AppSettings(_env_file=None)  # type: ignore[call-arg]
