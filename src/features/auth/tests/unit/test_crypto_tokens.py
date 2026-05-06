"""Unit tests for the password, JWT, and rate-limit primitives in the auth feature.

These tests exercise the building blocks in isolation (no DB, no FastAPI),
so a regression in any of them is easy to attribute to the specific
component rather than a broader integration issue.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.features.auth.application.crypto import (
    PasswordService,
    generate_opaque_token,
    hash_token,
)
from src.features.auth.application.errors import (
    InvalidTokenError,
    RateLimitExceededError,
)
from src.features.auth.application.jwt_tokens import AccessTokenService
from src.features.auth.application.rate_limit import FixedWindowRateLimiter
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


def test_password_hash_verifies_and_is_not_plaintext() -> None:
    service = PasswordService()
    password_hash = service.hash_password("CorrectHorseBattery123!")

    assert password_hash != "CorrectHorseBattery123!"
    assert service.verify_password(password_hash, "CorrectHorseBattery123!")
    assert not service.verify_password(password_hash, "wrong-password")


def test_opaque_token_hash_is_stable_without_storing_token() -> None:
    token = generate_opaque_token()

    assert token != hash_token(token)
    assert hash_token(token) == hash_token(token)


def test_access_token_requires_configured_audience() -> None:
    settings = AppSettings(
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
        auth_jwt_issuer="starter-tests",
        auth_jwt_audience="starter-api",
    )
    token_service = AccessTokenService(settings)

    token, expires_in = token_service.issue(
        subject=uuid4(), roles={"user"}, authz_version=1
    )

    assert expires_in > 0
    decoded = token_service.decode(token)
    assert decoded.authz_version == 1

    wrong_audience = AccessTokenService(
        settings.model_copy(update={"auth_jwt_audience": "other-api"})
    )
    with pytest.raises(InvalidTokenError):
        wrong_audience.decode(token)


def test_rate_limiter_rejects_after_window_limit() -> None:
    limiter = FixedWindowRateLimiter(max_attempts=2, window_seconds=60)

    limiter.check("client")
    limiter.check("client")

    with pytest.raises(RateLimitExceededError):
        limiter.check("client")
