"""End-to-end coverage for the ``/me`` profile endpoints.

The existing ``test_self_view_redaction``, ``test_self_deactivate``, and
``test_self_erase`` suites cover specific facets (field redaction,
cookie clearing, erasure pipeline). This module fills the remaining
gap called out in ``strengthen-test-contracts``: full happy-path and
auth-failure coverage of ``GET /me``, ``PATCH /me``, and ``DELETE /me``
against the fully wired FastAPI app.

Each request flows through the real HTTP layer, the principal resolver,
the users container, and the SQLite-backed user repository so a
regression anywhere in that pipeline surfaces here.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from features.authentication.tests.e2e.conftest import AuthTestContext

pytestmark = pytest.mark.e2e


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
    return str(response.json()["access_token"])


# ── GET /me ────────────────────────────────────────────────────────────────────


def test_get_me_returns_self_view_for_authenticated_user(
    client: TestClient,
) -> None:
    """GET /me MUST return the caller's profile fields."""
    _register(client, email="alice@example.com")
    token = _login(client, email="alice@example.com")

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["is_active"] is True
    # Sanity-check the schema includes the expected self-view fields.
    for field_name in ("id", "email", "is_active", "is_verified", "created_at"):
        assert field_name in body


def test_get_me_without_authentication_returns_401(
    client: TestClient,
) -> None:
    """An unauthenticated GET /me MUST be rejected."""
    response = client.get("/me")
    assert response.status_code == 401


def test_get_me_with_invalid_token_returns_401(
    client: TestClient,
) -> None:
    """A malformed bearer token MUST be rejected without leaking state."""
    response = client.get("/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


def test_get_me_after_deactivation_returns_401(
    client: TestClient,
) -> None:
    """A user deactivated mid-session MUST be denied on the next request.

    ``DELETE /me`` bumps ``authz_version`` and flips ``is_active=False``;
    the principal resolver re-reads the user row and rejects the stale
    token. This pins the cache-invalidation guarantee at the HTTP edge.
    """
    _register(client, email="zoe@example.com")
    token = _login(client, email="zoe@example.com")

    deactivate = client.delete("/me", headers={"Authorization": f"Bearer {token}"})
    assert deactivate.status_code == 204

    # The same access token must now be rejected. Even if the JWT has
    # not yet expired, the server-side deactivation invalidates it.
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ── PATCH /me ─────────────────────────────────────────────────────────────────


def test_patch_me_updates_email(client: TestClient) -> None:
    """A valid email update MUST change the persisted profile and echo back."""
    _register(client, email="old@example.com")
    token = _login(client, email="old@example.com")

    response = client.patch(
        "/me",
        json={"email": "new@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "new@example.com"

    # Confirm the change is persisted: a subsequent GET MUST see it.
    get_response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert get_response.status_code == 200
    assert get_response.json()["email"] == "new@example.com"


def test_patch_me_with_no_fields_is_a_noop(client: TestClient) -> None:
    """An empty PATCH body MUST succeed and leave the profile unchanged."""
    _register(client, email="bob@example.com")
    token = _login(client, email="bob@example.com")

    response = client.patch(
        "/me",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "bob@example.com"


def test_patch_me_with_email_already_taken_returns_409(
    client: TestClient,
) -> None:
    """Updating to a duplicate email MUST surface as 409 Conflict."""
    _register(client, email="taken@example.com")
    _register(client, email="other@example.com")
    token = _login(client, email="other@example.com")

    response = client.patch(
        "/me",
        json={"email": "taken@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


def test_patch_me_without_authentication_returns_401(
    client: TestClient,
) -> None:
    response = client.patch("/me", json={"email": "x@example.com"})
    assert response.status_code == 401


def test_patch_me_with_invalid_body_returns_422(client: TestClient) -> None:
    """A non-string email MUST be rejected by FastAPI's validation layer."""
    _register(client, email="bob@example.com")
    token = _login(client, email="bob@example.com")

    response = client.patch(
        "/me",
        json={"email": 12345},  # not a string
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ── DELETE /me ────────────────────────────────────────────────────────────────


def test_delete_me_returns_204_and_deactivates_user(
    auth_context: AuthTestContext,
) -> None:
    """DELETE /me MUST flip ``is_active`` to false in the persisted row."""
    _register(auth_context.client, email="kate@example.com")
    token = _login(auth_context.client, email="kate@example.com")

    response = auth_context.client.delete(
        "/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204

    # Verify the user row reflects the deactivation. The user repository
    # is exposed on the test context so e2e tests can inspect side
    # effects without going through an admin endpoint.
    user = auth_context.user_repository.get_by_email("kate@example.com")
    assert user is not None
    assert user.is_active is False


def test_delete_me_without_authentication_returns_401(
    client: TestClient,
) -> None:
    response = client.delete("/me")
    assert response.status_code == 401


def test_delete_me_twice_with_same_token_returns_401_on_second_call(
    client: TestClient,
) -> None:
    """The token used for the first DELETE MUST be invalidated.

    Both the ``is_active=False`` flip and the refresh-token family
    revocation happen inside one UoW, so replaying the access token is
    a deterministic 401 on the second attempt.
    """
    _register(client, email="liz@example.com")
    token = _login(client, email="liz@example.com")

    first = client.delete("/me", headers={"Authorization": f"Bearer {token}"})
    assert first.status_code == 204

    second = client.delete("/me", headers={"Authorization": f"Bearer {token}"})
    assert second.status_code == 401
