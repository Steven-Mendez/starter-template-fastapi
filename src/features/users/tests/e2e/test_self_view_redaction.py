"""End-to-end coverage for the self-view vs admin-view field split.

The ``hide-internal-fields-from-self-views`` proposal splits the user
projection into two response schemas: ``UserPublic`` (admin views) keeps
``authz_version`` because operators need the cache-invalidation counter,
while ``UserPublicSelf`` (``GET /me`` / ``PATCH /me``) redacts it so
clients cannot infer permission-change history (a role granted then
revoked).

These tests pin both halves of the contract through the real HTTP layer
so a regression on either side surfaces here:

* ``GET /me`` must NOT include ``authz_version``.
* ``GET /admin/users`` must include ``authz_version`` on every user
  object the page returns.
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


def test_get_me_does_not_expose_authz_version(client: TestClient) -> None:
    """``GET /me`` returns ``UserPublicSelf`` — ``authz_version`` is redacted.

    The counter would leak permission-change history (e.g. a role
    granted then revoked) to the user themselves. Admin views keep
    it; self-views must not.
    """
    _register(client)
    token = _login(client)

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert "authz_version" not in body, (
        "GET /me leaked the internal authz_version counter; the self-view "
        "schema must redact it."
    )
    # Sanity-check: the non-redacted fields are still present so we are
    # not passing this test by accident on a broken response shape.
    for retained in ("id", "email", "is_active", "is_verified", "created_at"):
        assert retained in body


def test_admin_users_listing_includes_authz_version_for_every_user(
    auth_context: AuthTestContext,
) -> None:
    """``GET /admin/users`` returns ``UserPublic`` — ``authz_version`` is kept.

    Operators need the cache-invalidation counter for cache reasoning
    when investigating permission state. The admin view must keep it
    on every row of the keyset-paginated page so the contract is not
    silently regressed by adapting only the self-view.
    """
    # Register at least one extra user so the page has more than the
    # bootstrapped system admin — the "every user" assertion is only
    # meaningful when there is more than one user object to check.
    _register(auth_context.client, "regular@example.com")

    admin_token = _login(auth_context.client, "admin@example.com", "AdminPassword123!")
    response = auth_context.client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    items = body["items"]
    assert len(items) >= 2, (
        "Expected the admin listing to surface both the bootstrap admin and "
        "the regular user just registered; got fewer rows."
    )
    for user_object in items:
        assert "authz_version" in user_object, (
            "GET /admin/users dropped authz_version from a user object; "
            "the admin view must continue to expose it."
        )
        assert isinstance(user_object["authz_version"], int)
