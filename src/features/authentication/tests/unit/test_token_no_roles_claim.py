"""Unit tests asserting that JWTs no longer carry a roles claim.

Under ReBAC, every authorization decision goes through the
``AuthorizationPort``; embedding roles in the token would teach a
contradicting pattern and create stale-roles drift.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest

from src.features.authentication.application.jwt_tokens import AccessTokenService
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit

_SECRET = "test-secret-key-with-at-least-32-bytes"


def _settings() -> AppSettings:
    return AppSettings(
        environment="test",
        auth_jwt_secret_key=_SECRET,
        auth_redis_url=None,
    )


def test_issued_token_has_no_roles_claim() -> None:
    service = AccessTokenService(_settings())
    token, _expires_in = service.issue(subject=uuid4(), authz_version=1)
    payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
    assert "roles" not in payload
    assert set(payload.keys()) == {"sub", "exp", "iat", "nbf", "jti", "authz_version"}


def test_legacy_token_with_roles_claim_still_decodes() -> None:
    """Tokens issued before this change carried a ``roles`` array; they must
    keep validating so a deployment cut-over does not log everyone out."""
    service = AccessTokenService(_settings())
    now = datetime.now(timezone.utc)
    subject = uuid4()
    legacy_payload = {
        "sub": str(subject),
        "exp": now + timedelta(minutes=10),
        "iat": now,
        "nbf": now,
        "jti": "legacy-jti",
        "authz_version": 1,
        "roles": ["admin", "manager"],
    }
    legacy_token = jwt.encode(legacy_payload, _SECRET, algorithm="HS256")

    decoded = service.decode(legacy_token)
    # The legacy claim is silently ignored; no attribute or shape change.
    assert not hasattr(decoded, "roles")
    assert decoded.subject == subject
    assert decoded.authz_version == 1
    assert decoded.token_id == "legacy-jti"
    # The slots layout has no room for legacy claims.
    assert isinstance(decoded.subject, UUID)
