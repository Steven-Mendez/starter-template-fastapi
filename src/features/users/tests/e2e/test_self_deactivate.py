"""End-to-end coverage for ``DELETE /me``.

Self-deactivation is a destructive, synchronous user action. In a single
response cycle the server must (1) revoke every refresh-token family for
the user inside the same Unit of Work as the ``is_active=False`` flip,
and (2) clear the browser-side refresh cookie. These tests pin both
behaviours through the real HTTP layer so a regression in either half
surfaces here.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e

# Cookie-authenticated endpoints enforce Origin-or-Referer (CSRF
# mitigation); ``TestClient`` does not send ``Origin`` by default, so
# the test sends the same header a browser would on its cross-origin
# POST.
_COOKIE_ORIGIN_HEADERS = {"Origin": "http://testserver"}


def _register(client: TestClient, email: str = "user@example.com") -> dict[str, Any]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "UserPassword123!"},
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def _login(
    client: TestClient,
    email: str = "user@example.com",
    password: str = "UserPassword123!",
) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert client.cookies.get("refresh_token")
    return str(response.json()["access_token"])


def test_delete_me_clears_refresh_cookie(client: TestClient) -> None:
    """``DELETE /me`` must emit ``Set-Cookie`` clearing the refresh cookie."""
    _register(client)
    token = _login(client)
    assert client.cookies.get("refresh_token") is not None

    response = client.delete("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    # Starlette's TestClient merges Set-Cookie headers into a single
    # comma-separated string when there are multiple values; checking
    # via raw headers preserves all of them.
    set_cookies = response.headers.get_list("set-cookie")
    assert any("refresh_token=" in c for c in set_cookies)
    assert any("Max-Age=0" in c for c in set_cookies)
    assert any("Path=/auth" in c for c in set_cookies)
    # The cookie jar should also reflect the deletion.
    assert client.cookies.get("refresh_token") is None


def test_refresh_after_self_deactivate_returns_401(client: TestClient) -> None:
    """Replaying a captured refresh cookie after ``DELETE /me`` must fail.

    Even if a client proxy strips ``Set-Cookie`` (so the browser keeps
    the cookie), the server-side refresh-token families have been
    revoked inside the same UoW as the deactivation. ``POST /auth/refresh``
    must reject the captured cookie with 401.
    """
    _register(client)
    token = _login(client)
    captured_cookie = client.cookies.get("refresh_token")
    assert captured_cookie is not None

    delete_response = client.delete("/me", headers={"Authorization": f"Bearer {token}"})
    assert delete_response.status_code == 204

    # Re-instate the captured cookie that the TestClient already cleared
    # when it observed the ``Max-Age=0`` Set-Cookie. This simulates a
    # client that retained the cookie through a stripping proxy.
    refresh_response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": captured_cookie},
        headers=_COOKIE_ORIGIN_HEADERS,
    )
    assert refresh_response.status_code == 401
    assert "access_token" not in refresh_response.text
