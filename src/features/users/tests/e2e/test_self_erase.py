"""End-to-end coverage for ``DELETE /me/erase`` and the admin erase route.

The flows are exercised against the fully wired FastAPI app from the
auth e2e fixtures, which sets up an in-process job queue dispatching
``erase_user`` inline. That means a successful 202 response is followed
by the actual scrub running before the test client returns control —
the assertions below check the post-scrub database state directly.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    CredentialTable,
    RefreshTokenTable,
)
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


def _admin_login(client: TestClient) -> str:
    return _login(
        client,
        email="admin@example.com",
        password="AdminPassword123!",
    )


def test_delete_me_erase_with_correct_password_returns_202(
    auth_context: AuthTestContext,
) -> None:
    """Correct password → 202, job_id present, scrub completes inline."""
    client = auth_context.client
    _register(client)
    token = _login(client)

    response = client.request(
        "DELETE",
        "/me/erase",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "UserPassword123!"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["job_id"]
    assert payload["estimated_completion_seconds"] == 60
    assert "Location" in response.headers

    # Inline dispatch means the scrub has run by the time we observe.
    with Session(auth_context.repository.engine) as session:
        stmt = select(AuthAuditEventTable).where(
            AuthAuditEventTable.event_type == "user.erased"
        )
        events = session.exec(stmt).all()
        assert any(
            (e[0] if isinstance(e, tuple) else e).user_id is not None for e in events
        ), "Expected a user.erased audit row"


def test_delete_me_erase_with_wrong_password_returns_401(
    auth_context: AuthTestContext,
) -> None:
    """Wrong password → 401 and no job enqueued."""
    client = auth_context.client
    _register(client)
    token = _login(client)

    response = client.request(
        "DELETE",
        "/me/erase",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "WrongPassword!"},
    )

    assert response.status_code == 401
    # No user.erased audit event should exist.
    with Session(auth_context.repository.engine) as session:
        stmt = select(AuthAuditEventTable).where(
            AuthAuditEventTable.event_type == "user.erased"
        )
        events = session.exec(stmt).all()
        assert not events, "No erasure event should be recorded on wrong-password"


def test_admin_erase_route_succeeds(auth_context: AuthTestContext) -> None:
    """Admin-gated erase route enqueues the job and returns 202."""
    client = auth_context.client
    body = _register(client, email="victim@example.com")
    user_id = body["id"]
    admin_token = _admin_login(client)

    response = client.post(
        f"/admin/users/{user_id}/erase",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "accepted"
    # Credentials for the target user are gone after the inline dispatch.
    with Session(auth_context.repository.engine) as session:
        stmt = select(CredentialTable)
        creds = [
            (c[0] if isinstance(c, tuple) else c) for c in session.exec(stmt).all()
        ]
        for cred in creds:
            assert str(cred.user_id) != user_id


def test_admin_erase_route_rejects_non_admin(
    auth_context: AuthTestContext,
) -> None:
    """Non-admin calling the admin route → 403."""
    client = auth_context.client
    _register(client, email="alice@example.com")
    body = _register(client, email="bob@example.com")
    other_id = body["id"]
    # alice's token; alice is not an admin.
    alice_token = _login(client, email="alice@example.com")

    response = client.post(
        f"/admin/users/{other_id}/erase",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert response.status_code == 403


def test_get_me_export_returns_signed_url(
    auth_context: AuthTestContext,
) -> None:
    """``GET /me/export`` returns a signed URL pointing at a JSON blob."""
    client = auth_context.client
    _register(client, email="export-user@example.com")
    token = _login(client, email="export-user@example.com")

    response = client.get("/me/export", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert "download_url" in body
    assert "expires_at" in body
    # ``FakeFileStorage`` issues ``memory://`` URLs; the blob exists under
    # the corresponding key.
    url = body["download_url"]
    assert url.startswith("memory://exports/")
    key = url.removeprefix("memory://")
    stored = auth_context.file_storage.objects[key]
    assert stored.content_type == "application/json"
    assert b'"user"' in stored.content


def test_re_register_with_original_email_after_erase(
    auth_context: AuthTestContext,
) -> None:
    """An erased email can be reclaimed by a fresh registration."""
    client = auth_context.client
    body = _register(client, email="reusable@example.com")
    original_id = body["id"]
    token = _login(client, email="reusable@example.com")

    erase_response = client.request(
        "DELETE",
        "/me/erase",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "UserPassword123!"},
    )
    assert erase_response.status_code == 202

    # Now register the same email — should succeed with a fresh user_id.
    register_response = client.post(
        "/auth/register",
        json={"email": "reusable@example.com", "password": "UserPassword123!"},
    )
    assert register_response.status_code == 201
    fresh_id = register_response.json()["id"]
    assert fresh_id != original_id


def test_erase_is_idempotent(auth_context: AuthTestContext) -> None:
    """A second admin erase on an already-erased user is a no-op (still 202)."""
    client = auth_context.client
    body = _register(client, email="twice@example.com")
    user_id = body["id"]
    admin_token = _admin_login(client)

    r1 = client.post(
        f"/admin/users/{user_id}/erase",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 202
    r2 = client.post(
        f"/admin/users/{user_id}/erase",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Idempotent on the use-case level; the HTTP response is still 202
    # (we accept the job; the handler is a no-op).
    assert r2.status_code == 202


def test_audit_metadata_is_scrubbed_after_erasure(
    auth_context: AuthTestContext,
) -> None:
    """Audit rows survive erasure; PII keys are absent from metadata."""
    client = auth_context.client
    body = _register(client, email="audit-target@example.com")
    user_id = body["id"]
    # Login produces an audit event with ip_address in metadata (the
    # FastAPI test client sets a default test client). Then erase.
    token = _login(client, email="audit-target@example.com")
    client.request(
        "DELETE",
        "/me/erase",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "UserPassword123!"},
    )

    from uuid import UUID

    target_uuid = UUID(user_id)
    with Session(auth_context.repository.engine) as session:
        stmt = select(AuthAuditEventTable).where(
            AuthAuditEventTable.user_id == target_uuid
        )
        rows = [(r[0] if isinstance(r, tuple) else r) for r in session.exec(stmt).all()]
        for row in rows:
            metadata = row.event_metadata or {}
            assert "ip_address" not in metadata
            assert "user_agent" not in metadata
            assert "family_id" not in metadata
            assert row.ip_address is None
            assert row.user_agent is None

        # Refresh tokens for the user are gone.
        refresh_stmt = select(RefreshTokenTable).where(
            RefreshTokenTable.user_id == target_uuid
        )
        refreshes = session.exec(refresh_stmt).all()
        assert not refreshes
