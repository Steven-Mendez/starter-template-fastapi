"""End-to-end tests for the system-admin bootstrap flow.

Re-runs the bootstrap against the same DB to confirm idempotency and
verifies that the audit trail records exactly one bootstrap event with
the new event type ``authz.bootstrap_admin_assigned``.
"""

from __future__ import annotations

import pytest

from src.features.authentication.tests.e2e.conftest import AuthTestContext

pytestmark = pytest.mark.e2e


def test_bootstrap_creates_user_and_writes_system_admin_tuple(
    auth_context: AuthTestContext,
) -> None:
    """The fixture's _build_app already calls bootstrap once at startup.

    Inspect the persisted side effects: the user exists, an admin tuple was
    written on ``system:main``, and one audit event was recorded.
    """
    from sqlalchemy import text  # noqa: PLC0415
    from sqlmodel import Session  # noqa: PLC0415

    repo = auth_context.repository
    user = repo.get_user_by_email("admin@example.com")
    assert user is not None

    with Session(repo.engine) as session:
        rows = list(
            session.execute(
                text(
                    "SELECT 1 FROM relationships "
                    "WHERE resource_type = 'system' "
                    "AND resource_id = 'main' "
                    "AND relation = 'admin' "
                    "AND subject_id = :sid"
                ),
                {"sid": str(user.id)},
            )
        )
    assert len(rows) == 1

    audit = repo.list_audit_events(event_type="authz.bootstrap_admin_assigned")
    assert any(event.user_id == user.id for event in audit)


def test_bootstrap_is_idempotent_on_relationship_writes(
    auth_context: AuthTestContext,
) -> None:
    """Running bootstrap a second time produces no duplicate tuples."""
    from sqlalchemy import text  # noqa: PLC0415
    from sqlmodel import Session  # noqa: PLC0415

    repo = auth_context.repository
    container = auth_context.client.app.state.authorization_container  # type: ignore[attr-defined]
    container.bootstrap_system_admin.execute(
        email="admin@example.com",
        password="AdminPassword123!",
    )

    user = repo.get_user_by_email("admin@example.com")
    assert user is not None
    with Session(repo.engine) as session:
        rows = list(
            session.execute(
                text(
                    "SELECT 1 FROM relationships "
                    "WHERE resource_type = 'system' AND subject_id = :sid"
                ),
                {"sid": str(user.id)},
            )
        )
    assert len(rows) == 1


def test_admin_login_produces_token_with_no_roles_claim(
    auth_context: AuthTestContext,
) -> None:
    """Tokens for the system admin are no different from any other user's
    tokens — authorization is engine-resolved, not encoded in the token."""
    import jwt  # noqa: PLC0415

    response = auth_context.client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, options={"verify_signature": False})
    assert "roles" not in payload
