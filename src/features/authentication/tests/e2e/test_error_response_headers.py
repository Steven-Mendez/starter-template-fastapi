"""End-to-end checks that auth error responses carry the right HTTP headers.

These tests exercise the real auth router so we are sure the headers the
dependency / error-mapping layer attaches actually make it out the door:

- 401 from a missing ``Authorization`` header → ``WWW-Authenticate: Bearer``
- 401 from a missing ``Authorization`` header → non-empty ``X-Request-ID``
- 429 from the login rate limiter → ``Retry-After: N`` where ``N`` is a
  positive integer.
"""

from __future__ import annotations

import pytest

from features.authentication.tests.e2e.conftest import AuthTestContext

pytestmark = pytest.mark.e2e

_RATE_LIMIT_ATTEMPTS_BEFORE_429 = 5


def test_401_missing_bearer_carries_www_authenticate_bearer(
    auth_context: AuthTestContext,
) -> None:
    """RFC 7235 challenge: protected route without Authorization → Bearer challenge."""
    resp = auth_context.client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_401_missing_bearer_carries_request_id(
    auth_context: AuthTestContext,
) -> None:
    """``RequestContextMiddleware`` stamps every response with a request id."""
    resp = auth_context.client.get("/auth/me")
    assert resp.status_code == 401
    request_id = resp.headers.get("X-Request-ID")
    assert request_id is not None
    assert request_id != ""


def test_429_login_rate_limit_carries_retry_after(
    auth_context_rate_limited: AuthTestContext,
) -> None:
    """The 429 from a tripped login limit MUST include ``Retry-After: N>0``."""
    client = auth_context_rate_limited.client
    body = {"email": "user@example.com", "password": "wrong-password"}
    for _ in range(_RATE_LIMIT_ATTEMPTS_BEFORE_429):
        response = client.post("/auth/login", json=body)
        assert response.status_code == 401
    blocked = client.post("/auth/login", json=body)
    assert blocked.status_code == 429
    retry_after = blocked.headers.get("Retry-After")
    assert retry_after is not None
    parsed = int(retry_after)
    assert parsed > 0
