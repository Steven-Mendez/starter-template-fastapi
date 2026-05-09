"""End-to-end coverage for the public auth flows.

Each test drives the real FastAPI app through ``TestClient`` and asserts
on both HTTP responses and persistence side effects, so a regression in
any layer (router, service, repository) surfaces here.
"""

from __future__ import annotations

import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.features.auth.tests.e2e.conftest import AuthTestContext

pytestmark = pytest.mark.e2e

_RATE_LIMIT_ATTEMPTS_BEFORE_429 = 5


def _register(client: TestClient, email: str = "user@example.com") -> dict:
    """Register a regular user with a known password and return the response body."""
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "UserPassword123!"},
    )
    assert response.status_code == 201
    return response.json()


def _login(
    client: TestClient,
    email: str = "user@example.com",
    password: str = "UserPassword123!",
) -> str:
    """Log in and return the access token, asserting the refresh cookie was set."""
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert client.cookies.get("refresh_token")
    return str(response.json()["access_token"])


def test_register_login_me_refresh_logout_flow(client: TestClient) -> None:
    user = _register(client)
    token = _login(client)

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"
    assert "password_hash" not in me.text
    assert user["email"] == "user@example.com"

    old_refresh = client.cookies.get("refresh_token")
    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != token
    assert client.cookies.get("refresh_token") != old_refresh

    logout = client.post("/auth/logout")
    assert logout.status_code == 200
    assert client.cookies.get("refresh_token") is None


def test_login_rate_limit_returns_429_after_repeated_attempts(
    auth_context_rate_limited: AuthTestContext,
) -> None:
    client = auth_context_rate_limited.client
    body = {"email": "user@example.com", "password": "wrong-password"}
    for _ in range(_RATE_LIMIT_ATTEMPTS_BEFORE_429):
        response = client.post("/auth/login", json=body)
        assert response.status_code == 401
    blocked = client.post("/auth/login", json=body)
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Rate limit exceeded"


def test_register_rate_limit_returns_429_after_repeated_attempts(
    auth_context_rate_limited: AuthTestContext,
) -> None:
    client = auth_context_rate_limited.client
    for i in range(_RATE_LIMIT_ATTEMPTS_BEFORE_429):
        response = client.post(
            "/auth/register",
            json={"email": f"user-{i}@example.com", "password": "UserPassword123!"},
        )
        assert response.status_code == 201
    blocked = client.post(
        "/auth/register",
        json={"email": "blocked@example.com", "password": "UserPassword123!"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Rate limit exceeded"


def test_duplicate_registration_and_invalid_login_are_safe(client: TestClient) -> None:
    _register(client)

    duplicate = client.post(
        "/auth/register",
        json={"email": "USER@example.com", "password": "UserPassword123!"},
    )
    assert duplicate.status_code == 409

    invalid = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid credentials"


def test_registration_rejects_weak_password(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "password123456"},
    )
    assert response.status_code == 422


def test_registration_accepts_complex_password(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "strong@example.com", "password": "Passw0rd!xyz!"},
    )
    assert response.status_code == 201


def test_unverified_user_cannot_login_when_required(
    auth_context_email_verification_required: AuthTestContext,
) -> None:
    client = auth_context_email_verification_required.client
    _register(client, "verify-required@example.com")

    response = client.post(
        "/auth/login",
        json={"email": "verify-required@example.com", "password": "UserPassword123!"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Email not verified"


def test_refresh_reuse_revokes_family(client: TestClient) -> None:
    _register(client)
    _login(client)
    old_refresh = client.cookies.get("refresh_token")
    assert old_refresh is not None

    first_refresh = client.post("/auth/refresh")
    assert first_refresh.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh is not None

    reused = client.post("/auth/refresh", cookies={"refresh_token": old_refresh})
    assert reused.status_code == 401

    family_revoked = client.post(
        "/auth/refresh", cookies={"refresh_token": new_refresh}
    )
    assert family_revoked.status_code == 401


def test_logout_all_revokes_all_sessions(client: TestClient) -> None:
    _register(client)
    token = _login(client)

    response = client.post(
        "/auth/logout-all", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    refresh = client.post("/auth/refresh")
    assert refresh.status_code == 401


def test_missing_token_is_401_and_user_without_permission_is_403(
    client: TestClient,
) -> None:
    missing = client.get("/auth/me")
    assert missing.status_code == 401

    _register(client)
    token = _login(client)
    forbidden = client.get("/admin/roles", headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403


def test_inactive_user_with_valid_token_is_403(auth_context: AuthTestContext) -> None:
    client = auth_context.client
    user = _register(client)
    token = _login(client)
    auth_context.repository.set_user_active(UUID(user["id"]), False)

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_inactive_user_login_returns_403(auth_context: AuthTestContext) -> None:
    client = auth_context.client
    user = _register(client, "inactive-login@example.com")
    auth_context.repository.set_user_active(UUID(user["id"]), False)

    response = client.post(
        "/auth/login",
        json={"email": "inactive-login@example.com", "password": "UserPassword123!"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account inactive"


def test_password_reset_and_email_verification(client: TestClient) -> None:
    _register(client)

    forgot = client.post("/auth/password/forgot", json={"email": "user@example.com"})
    assert forgot.status_code == 200
    reset_token = forgot.json()["dev_token"]
    assert reset_token

    reset = client.post(
        "/auth/password/reset",
        json={"token": reset_token, "new_password": "NewUserPassword123!"},
    )
    assert reset.status_code == 200
    reused_reset = client.post(
        "/auth/password/reset",
        json={"token": reset_token, "new_password": "NewUserPassword123!"},
    )
    assert reused_reset.status_code == 400
    assert reused_reset.json()["detail"] == "Token already used"

    token = _login(client, password="NewUserPassword123!")
    verify_request = client.post(
        "/auth/email/verify/request",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_request.status_code == 200
    verify_token = verify_request.json()["dev_token"]

    verify = client.post("/auth/email/verify", json={"token": verify_token})
    assert verify.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["is_verified"] is True


def test_internal_token_omission_does_not_emit_per_request_warning(
    auth_context_internal_tokens_hidden: AuthTestContext,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Per-request warnings on every password-reset request used to spam
    # production logs. The container now logs once at startup; here we
    # confirm the request path stays quiet while still suppressing the token.
    client = auth_context_internal_tokens_hidden.client
    _register(client)
    caplog.set_level(logging.WARNING, logger="src.features.auth.application.services")

    forgot = client.post("/auth/password/forgot", json={"email": "user@example.com"})

    assert forgot.status_code == 200
    assert forgot.json()["dev_token"] is None
    assert "no delivery provider" not in caplog.text


def test_stale_token_returns_401_with_invalid_token_detail(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client

    # Register a regular user and capture their access token.
    _register(client)
    user_token = _login(client)

    # Log in as the seeded super-admin.
    admin_resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    assert admin_resp.status_code == 200
    admin_token = admin_resp.json()["access_token"]

    # Find the user's ID and a role to assign.
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    users = client.get("/admin/users", headers=admin_headers)
    assert users.status_code == 200
    user_id = next(u["id"] for u in users.json() if u["email"] == "user@example.com")

    roles = client.get("/admin/roles", headers=admin_headers)
    assert roles.status_code == 200
    manager_role_id = next(r["id"] for r in roles.json() if r["name"] == "manager")

    # Assign the manager role, which bumps the user's authz_version.
    assign = client.post(
        f"/admin/users/{user_id}/roles",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role_id": manager_role_id},
    )
    assert assign.status_code == 201

    # The old token now carries a stale authz_version — it must be rejected
    # with a machine-readable code so clients know to re-authenticate rather
    # than assume the token is structurally invalid.
    stale = client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    assert stale.status_code == 401
    assert stale.json()["code"] == "stale_token"
    assert "stale" in stale.json()["detail"].lower()


def test_refresh_token_rejected_after_logout(client: TestClient) -> None:
    _register(client)
    _login(client)

    token_before_logout = client.cookies.get("refresh_token")
    assert token_before_logout is not None

    logout_resp = client.post("/auth/logout")
    assert logout_resp.status_code == 200
    assert client.cookies.get("refresh_token") is None

    post_logout_attempt = client.post(
        "/auth/refresh",
        cookies={"refresh_token": token_before_logout},
    )
    assert post_logout_attempt.status_code == 401
