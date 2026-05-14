"""End-to-end tests for admin route authorization under ReBAC."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from features.authentication.tests.e2e.conftest import AuthTestContext

pytestmark = pytest.mark.e2e


def _register(client: TestClient, email: str) -> dict[str, Any]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "UserPassword123!"},
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return str(response.json()["access_token"])


def test_system_admin_can_list_users(auth_context: AuthTestContext) -> None:
    token = _login(auth_context.client, "admin@example.com", "AdminPassword123!")
    response = auth_context.client.get(
        "/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    emails = {u["email"] for u in body["items"]}
    assert "admin@example.com" in emails


def test_system_admin_can_read_audit_log(auth_context: AuthTestContext) -> None:
    token = _login(auth_context.client, "admin@example.com", "AdminPassword123!")
    response = auth_context.client.get(
        "/admin/audit-log", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "count" in body
    assert "limit" in body


def test_non_admin_user_gets_403_on_admin_users(
    auth_context: AuthTestContext,
) -> None:
    _register(auth_context.client, "regular@example.com")
    token = _login(auth_context.client, "regular@example.com", "UserPassword123!")
    response = auth_context.client.get(
        "/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_non_admin_user_gets_403_on_admin_audit_log(
    auth_context: AuthTestContext,
) -> None:
    _register(auth_context.client, "regular2@example.com")
    token = _login(auth_context.client, "regular2@example.com", "UserPassword123!")
    response = auth_context.client.get(
        "/admin/audit-log", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/admin/roles"),
        ("PATCH", "/admin/roles/00000000-0000-0000-0000-000000000000"),
        ("GET", "/admin/roles"),
        ("POST", "/admin/permissions"),
        ("GET", "/admin/permissions"),
        ("POST", "/admin/roles/00000000-0000-0000-0000-000000000000/permissions"),
        (
            "DELETE",
            "/admin/roles/00000000-0000-0000-0000-000000000000/permissions/"
            "00000000-0000-0000-0000-000000000000",
        ),
        ("POST", "/admin/users/00000000-0000-0000-0000-000000000000/roles"),
        (
            "DELETE",
            "/admin/users/00000000-0000-0000-0000-000000000000/roles/"
            "00000000-0000-0000-0000-000000000000",
        ),
    ],
)
def test_removed_rbac_routes_return_404(
    auth_context: AuthTestContext, method: str, path: str
) -> None:
    """All RBAC management routes were removed under ReBAC."""
    token = _login(auth_context.client, "admin@example.com", "AdminPassword123!")
    response = auth_context.client.request(
        method, path, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


def test_admin_endpoints_require_authentication(
    auth_context: AuthTestContext,
) -> None:
    """Missing credentials should always 401, never 403."""
    no_auth = auth_context.client.get("/admin/users")
    assert no_auth.status_code == 401
    no_auth_audit = auth_context.client.get("/admin/audit-log")
    assert no_auth_audit.status_code == 401
