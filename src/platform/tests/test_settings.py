"""Unit tests for :class:`AppSettings` defaults, env overrides, and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.platform.config.settings import AppSettings, get_settings

pytestmark = pytest.mark.unit

_VALID_PROD_ENV = {
    "APP_ENVIRONMENT": "production",
    "APP_ENABLE_DOCS": "false",
    "APP_AUTH_JWT_SECRET_KEY": "a-secret-at-least-32-chars-long!!",
    "APP_CORS_ORIGINS": '["https://example.com"]',
    "APP_AUTH_COOKIE_SECURE": "true",
}


def test_defaults_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "APP_ENVIRONMENT",
        "APP_ENABLE_DOCS",
        "APP_CORS_ORIGINS",
        "APP_TRUSTED_HOSTS",
        "APP_WRITE_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "development"
    assert s.enable_docs is True
    assert s.cors_origins == ["*"]
    assert s.write_api_key is None


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
