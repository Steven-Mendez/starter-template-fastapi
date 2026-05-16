"""Unit tests for :class:`EmailSettings` construction and validation.

After ROADMAP ETAPA I step 4 (Resend removed, AWS SES not yet added)
``console`` is the only accepted email backend. These tests pin the
construction guard and the production refusal so the removed backends
cannot silently reappear.
"""

from __future__ import annotations

import pytest

from features.email.composition.settings import EmailSettings

pytestmark = pytest.mark.unit


def test_console_backend_constructs() -> None:
    settings = EmailSettings.from_app_settings(
        backend="console", from_address="no-reply@example.com"
    )
    assert settings.backend == "console"
    assert settings.from_address == "no-reply@example.com"
    assert settings.console_log_bodies is False


@pytest.mark.parametrize("backend", ["resend", "smtp", "ses", "bogus"])
def test_unknown_backend_value_rejected(backend: str) -> None:
    """Any non-``console`` value raises, and the message names only ``console``.

    The message must NOT advertise a removed backend (``resend`` /
    ``smtp``) as if it were a selectable option (email capability spec).
    """
    with pytest.raises(ValueError, match="APP_EMAIL_BACKEND") as exc_info:
        EmailSettings.from_app_settings(backend=backend)
    message = str(exc_info.value)
    assert "'console'" in message, message
    assert "resend" not in message.lower(), message
    assert "smtp" not in message.lower(), message


def test_production_refuses_console_without_naming_removed_backend() -> None:
    """``validate_production`` still refuses ``console``; names no removed backend.

    There is no production-capable email backend until AWS SES arrives
    at a later roadmap step, so the only value (``console``) is refused
    in production and the message must not instruct the operator to
    configure ``resend`` or ``smtp``.
    """
    settings = EmailSettings.from_app_settings(backend="console")
    errors: list[str] = []
    settings.validate_production(errors)
    assert len(errors) == 1, errors
    lowered = errors[0].lower()
    assert "app_email_backend" in lowered
    assert "console" in lowered
    assert "resend" not in lowered
    assert "smtp" not in lowered


def test_validate_is_a_noop() -> None:
    """``validate`` no longer has backend-specific checks (Resend removed)."""
    settings = EmailSettings.from_app_settings(backend="console")
    errors: list[str] = []
    settings.validate(errors)
    assert errors == []
