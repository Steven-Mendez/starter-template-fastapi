"""Unit tests for :class:`OutboxSettings` retention/prune fields.

Covers the validator additions for the prune cron's three knobs and
the derived ``dedup_retention_seconds`` property.
"""

from __future__ import annotations

import logging

import pytest

from features.outbox.composition.settings import OutboxSettings

pytestmark = pytest.mark.unit


def _settings(**overrides: object) -> OutboxSettings:
    """Build an :class:`OutboxSettings` with the prune-relevant defaults overridable."""
    base: dict[str, object] = {
        "enabled": True,
        "relay_interval_seconds": 5.0,
        "claim_batch_size": 100,
        "max_attempts": 8,
        "retry_base_seconds": 30.0,
        "retry_max_seconds": 900.0,
        "worker_id": "test:1",
        "retention_delivered_days": 7,
        "retention_failed_days": 30,
        "prune_batch_size": 1000,
    }
    base.update(overrides)
    return OutboxSettings(**base)  # type: ignore[arg-type]


def test_defaults_validate_without_errors() -> None:
    settings = _settings()
    errors: list[str] = []
    settings.validate(errors)
    assert errors == []


def test_negative_retention_delivered_is_rejected() -> None:
    errors: list[str] = []
    _settings(retention_delivered_days=0).validate(errors)
    assert any("RETENTION_DELIVERED_DAYS" in e for e in errors)
    errors.clear()
    _settings(retention_delivered_days=-1).validate(errors)
    assert any("RETENTION_DELIVERED_DAYS" in e for e in errors)


def test_negative_retention_failed_is_rejected() -> None:
    errors: list[str] = []
    _settings(retention_failed_days=0).validate(errors)
    assert any("RETENTION_FAILED_DAYS" in e for e in errors)


def test_negative_prune_batch_size_is_rejected() -> None:
    errors: list[str] = []
    _settings(prune_batch_size=0).validate(errors)
    assert any("PRUNE_BATCH_SIZE" in e for e in errors)


def test_failed_lt_delivered_emits_warning_not_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed-retention shorter than delivered-retention is a warning, not an error."""
    settings = _settings(retention_delivered_days=10, retention_failed_days=3)
    errors: list[str] = []
    with caplog.at_level(logging.WARNING, logger="features.outbox.settings"):
        settings.validate(errors)
    assert errors == []
    assert any("RETENTION_FAILED_DAYS" in record.message for record in caplog.records)


def test_dedup_retention_seconds_is_twice_retry_max() -> None:
    settings = _settings(retry_max_seconds=900.0)
    assert settings.dedup_retention_seconds == 1800.0


def test_from_app_settings_reads_new_fields() -> None:
    """Smoke: the flat-kwargs constructor populates the three new fields."""
    settings = OutboxSettings.from_app_settings(
        enabled=True,
        retention_delivered_days=14,
        retention_failed_days=45,
        prune_batch_size=2500,
    )
    assert settings.retention_delivered_days == 14
    assert settings.retention_failed_days == 45
    assert settings.prune_batch_size == 2500
    # Defaults still flow for the unspecified knobs.
    assert settings.claim_batch_size == 100
