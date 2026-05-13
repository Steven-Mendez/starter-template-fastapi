"""Email length is capped at the RFC 5321 practical limit (254 chars)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from features.authentication.adapters.inbound.http.schemas import (
    LoginRequest,
    PasswordForgotRequest,
    RegisterRequest,
)

pytestmark = pytest.mark.unit


def _email_at_length(length: int) -> str:
    # Build an address whose total length is exactly ``length``.
    suffix = "@example.com"
    local_length = length - len(suffix)
    assert local_length >= 1
    return ("a" * local_length) + suffix


def test_register_accepts_email_at_254() -> None:
    RegisterRequest(email=_email_at_length(254), password="UserPassword123!")


def test_register_rejects_email_at_255() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email=_email_at_length(255), password="UserPassword123!")


def test_login_rejects_email_at_255() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email=_email_at_length(255), password="x")


def test_password_forgot_rejects_email_at_255() -> None:
    with pytest.raises(ValidationError):
        PasswordForgotRequest(email=_email_at_length(255))
