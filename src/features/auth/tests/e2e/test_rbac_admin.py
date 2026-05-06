"""End-to-end coverage for the admin RBAC surface (``/admin/...`` endpoints)."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.features.auth.tests.e2e.conftest import AuthTestContext

pytestmark = pytest.mark.e2e


def _login_admin(client: TestClient) -> str:
    """Log in with the seeded super-admin credentials and return the access token."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    """Return an ``Authorization`` header dict for the given bearer token."""
    return {"Authorization": f"Bearer {token}"}


def _register_user(client: TestClient, email: str) -> str:
    """Register a regular user and return the resulting user ID as a string."""
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "UserPassword123!"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_admin_can_manage_roles_permissions_and_user_assignments(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    admin_token = _login_admin(client)

    roles = client.get("/admin/roles", headers=_auth(admin_token))
    assert roles.status_code == 200

    role = client.post(
        "/admin/roles",
        headers=_auth(admin_token),
        json={"name": "auditor", "description": "Can audit records"},
    )
    assert role.status_code == 201
    role_id = role.json()["id"]

    permission = client.post(
        "/admin/permissions",
        headers=_auth(admin_token),
        json={"name": "reports:read", "description": "Read reports"},
    )
    assert permission.status_code == 201
    permission_id = permission.json()["id"]

    assign_permission = client.post(
        f"/admin/roles/{role_id}/permissions",
        headers=_auth(admin_token),
        json={"permission_id": permission_id},
    )
    assert assign_permission.status_code == 201

    permissions = client.get("/admin/permissions", headers=_auth(admin_token)).json()
    roles_read_id = next(
        item["id"] for item in permissions if item["name"] == "roles:read"
    )
    grant_roles_read = client.post(
        f"/admin/roles/{role_id}/permissions",
        headers=_auth(admin_token),
        json={"permission_id": roles_read_id},
    )
    assert grant_roles_read.status_code == 201

    user_id = _register_user(client, "auditor@example.com")
    assign_role = client.post(
        f"/admin/users/{user_id}/roles",
        headers=_auth(admin_token),
        json={"role_id": role_id},
    )
    assert assign_role.status_code == 201

    user_token = client.post(
        "/auth/login",
        json={"email": "auditor@example.com", "password": "UserPassword123!"},
    ).json()["access_token"]
    allowed = client.get("/admin/roles", headers=_auth(user_token))
    assert allowed.status_code == 200

    remove_permission = client.delete(
        f"/admin/roles/{role_id}/permissions/{permission_id}",
        headers=_auth(admin_token),
    )
    assert remove_permission.status_code == 204

    remove_role = client.delete(
        f"/admin/users/{user_id}/roles/{role_id}",
        headers=_auth(admin_token),
    )
    assert remove_role.status_code == 204

    events = auth_context.repository.list_audit_events()
    event_types = {event.event_type for event in events}
    assert "rbac.role_created" in event_types
    assert "rbac.permission_created" in event_types
    assert "rbac.role_permission_added" in event_types
    assert "rbac.user_role_added" in event_types


def test_admin_can_list_users(client: TestClient) -> None:
    admin_token = _login_admin(client)
    _register_user(client, "reader@example.com")

    response = client.get("/admin/users", headers=_auth(admin_token))
    assert response.status_code == 200
    emails = [item["email"] for item in response.json()]
    assert "admin@example.com" in emails
    assert "reader@example.com" in emails


def test_inactive_role_does_not_grant_permissions(client: TestClient) -> None:
    admin_token = _login_admin(client)
    role = client.post(
        "/admin/roles",
        headers=_auth(admin_token),
        json={"name": "readonly_ops"},
    ).json()
    permissions = client.get("/admin/permissions", headers=_auth(admin_token)).json()
    roles_read_id = next(
        item["id"] for item in permissions if item["name"] == "roles:read"
    )
    client.post(
        f"/admin/roles/{role['id']}/permissions",
        headers=_auth(admin_token),
        json={"permission_id": roles_read_id},
    )
    user_id = _register_user(client, "inactive-role@example.com")
    client.post(
        f"/admin/users/{user_id}/roles",
        headers=_auth(admin_token),
        json={"role_id": role["id"]},
    )

    patch = client.patch(
        f"/admin/roles/{role['id']}",
        headers=_auth(admin_token),
        json={"is_active": False},
    )
    assert patch.status_code == 200

    user_token = client.post(
        "/auth/login",
        json={"email": "inactive-role@example.com", "password": "UserPassword123!"},
    ).json()["access_token"]
    forbidden = client.get("/admin/roles", headers=_auth(user_token))
    assert forbidden.status_code == 403


def test_duplicate_role_and_permission_are_rejected(client: TestClient) -> None:
    admin_token = _login_admin(client)

    first_role = client.post(
        "/admin/roles", headers=_auth(admin_token), json={"name": "dupe_role"}
    )
    second_role = client.post(
        "/admin/roles", headers=_auth(admin_token), json={"name": "dupe_role"}
    )
    assert first_role.status_code == 201
    assert second_role.status_code == 409

    first_permission = client.post(
        "/admin/permissions",
        headers=_auth(admin_token),
        json={"name": "dupes:read"},
    )
    second_permission = client.post(
        "/admin/permissions",
        headers=_auth(admin_token),
        json={"name": "dupes:read"},
    )
    assert first_permission.status_code == 201
    assert second_permission.status_code == 409


def test_role_changes_make_existing_access_token_stale(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    admin_token = _login_admin(client)
    role = client.post(
        "/admin/roles", headers=_auth(admin_token), json={"name": "stale_reader"}
    ).json()
    permissions = client.get("/admin/permissions", headers=_auth(admin_token)).json()
    roles_read_id = next(
        item["id"] for item in permissions if item["name"] == "roles:read"
    )
    client.post(
        f"/admin/roles/{role['id']}/permissions",
        headers=_auth(admin_token),
        json={"permission_id": roles_read_id},
    )
    user_id = _register_user(client, "stale@example.com")
    client.post(
        f"/admin/users/{user_id}/roles",
        headers=_auth(admin_token),
        json={"role_id": role["id"]},
    )

    user_token = client.post(
        "/auth/login",
        json={"email": "stale@example.com", "password": "UserPassword123!"},
    ).json()["access_token"]
    auth_context.repository.increment_user_authz_version(UUID(user_id))

    stale = client.get("/admin/roles", headers=_auth(user_token))
    assert stale.status_code == 401
