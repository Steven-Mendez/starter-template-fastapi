"""Unit tests verifying that JWT decode respects the configured clock-skew leeway."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from src.features.auth.application.errors import InvalidTokenError
from src.features.auth.application.jwt_tokens import AccessTokenService
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit

_SECRET = "test-secret-key-with-at-least-32-bytes"


def _settings(leeway: int) -> AppSettings:
    return AppSettings(
        environment="test",
        auth_jwt_secret_key=_SECRET,
        auth_jwt_leeway_seconds=leeway,
        auth_redis_url=None,
    )


def _expired_token(seconds_ago: int) -> str:
    """Create a real HS256 token whose exp is ``seconds_ago`` in the past."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid4()),
        "exp": now - timedelta(seconds=seconds_ago),
        "iat": now - timedelta(seconds=seconds_ago + 1),
        "nbf": now - timedelta(seconds=seconds_ago + 1),
        "jti": str(uuid4()),
        "roles": [],
        "authz_version": 1,
    }
    return jwt.encode(payload, _SECRET, algorithm="HS256")


def test_token_within_leeway_is_accepted() -> None:
    svc = AccessTokenService(_settings(leeway=10))
    # Token expired 5 s ago — within the 10 s leeway window.
    token = _expired_token(seconds_ago=5)
    result = svc.decode(token)
    assert result is not None


def test_token_outside_leeway_is_rejected() -> None:
    svc = AccessTokenService(_settings(leeway=10))
    # Token expired 20 s ago — outside the 10 s leeway window.
    token = _expired_token(seconds_ago=20)
    with pytest.raises(InvalidTokenError):
        svc.decode(token)


def test_zero_leeway_rejects_any_expired_token() -> None:
    svc = AccessTokenService(_settings(leeway=0))
    token = _expired_token(seconds_ago=1)
    with pytest.raises(InvalidTokenError):
        svc.decode(token)
