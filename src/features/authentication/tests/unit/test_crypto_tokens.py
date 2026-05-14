"""Unit tests for the password, JWT, and rate-limit primitives in the auth feature.

These tests exercise the building blocks in isolation (no DB, no FastAPI),
so a regression in any of them is easy to attribute to the specific
component rather than a broader integration issue.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app_platform.config.settings import AppSettings
from features.authentication.application.crypto import (
    PasswordService,
    generate_opaque_token,
    hash_token,
)
from features.authentication.application.errors import (
    InvalidTokenError,
    RateLimitExceededError,
)
from features.authentication.application.jwt_tokens import AccessTokenService
from features.authentication.application.rate_limit import FixedWindowRateLimiter

pytestmark = pytest.mark.unit


def test_password_service_pins_argon2_parameters() -> None:
    """Task 4.3: the PasswordService MUST construct PasswordHasher with the
    OWASP-recommended Argon2id parameters explicitly, not the library default.

    Two production deploys with different ``argon2-cffi`` versions would
    otherwise rehash at materially different cost. Pinning makes the
    parameters a reviewable change rather than a silent upgrade artefact.
    """
    service = PasswordService()
    hasher = service._hasher

    assert hasher.time_cost == 3, (
        f"time_cost must be pinned to 3 (got {hasher.time_cost})"
    )
    assert hasher.memory_cost == 65536, (
        f"memory_cost must be pinned to 65536 KiB (got {hasher.memory_cost})"
    )
    assert hasher.parallelism == 4, (
        f"parallelism must be pinned to 4 (got {hasher.parallelism})"
    )
    assert hasher.hash_len == 32, (
        f"hash_len must be pinned to 32 bytes (got {hasher.hash_len})"
    )
    assert hasher.salt_len == 16, (
        f"salt_len must be pinned to 16 bytes (got {hasher.salt_len})"
    )


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

    token, expires_in = token_service.issue(subject=uuid4(), authz_version=1)

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
