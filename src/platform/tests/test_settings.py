"""Unit tests for :class:`AppSettings` defaults, env overrides, and validation."""

from __future__ import annotations

import pytest

from src.platform.config.settings import AppSettings, get_settings

pytestmark = pytest.mark.unit


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
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("APP_ENABLE_DOCS", "false")
    s = AppSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "production"
    assert s.enable_docs is False


def test_invalid_environment_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    from pydantic import ValidationError

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
