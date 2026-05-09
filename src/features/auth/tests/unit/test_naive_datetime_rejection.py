"""Auth domain models reject naive datetimes at construction."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.features.auth.domain.models import (
    AuditEvent,
    InternalToken,
    Permission,
    RefreshToken,
    Role,
    User,
)

pytestmark = pytest.mark.unit


_AWARE = datetime(2026, 1, 1, tzinfo=timezone.utc)
_NAIVE = datetime(2026, 1, 1)


def test_user_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="User.created_at"):
        User(
            id=uuid4(),
            email="user@example.com",
            password_hash="x",
            is_active=True,
            is_verified=True,
            authz_version=1,
            created_at=_NAIVE,
            updated_at=_AWARE,
            last_login_at=None,
        )


def test_user_rejects_naive_last_login_at() -> None:
    with pytest.raises(ValueError, match="User.last_login_at"):
        User(
            id=uuid4(),
            email="user@example.com",
            password_hash="x",
            is_active=True,
            is_verified=True,
            authz_version=1,
            created_at=_AWARE,
            updated_at=_AWARE,
            last_login_at=_NAIVE,
        )


def test_role_rejects_naive() -> None:
    with pytest.raises(ValueError, match="Role.created_at"):
        Role(
            id=uuid4(),
            name="r",
            description=None,
            is_active=True,
            created_at=_NAIVE,
            updated_at=_AWARE,
        )


def test_permission_rejects_naive() -> None:
    with pytest.raises(ValueError, match="Permission.updated_at"):
        Permission(
            id=uuid4(),
            name="p:read",
            description=None,
            created_at=_AWARE,
            updated_at=_NAIVE,
        )


def test_refresh_token_rejects_naive_expires() -> None:
    with pytest.raises(ValueError, match="RefreshToken.expires_at"):
        RefreshToken(
            id=uuid4(),
            user_id=uuid4(),
            token_hash="h",
            family_id=uuid4(),
            expires_at=_NAIVE,
            revoked_at=None,
            replaced_by_token_id=None,
            created_at=_AWARE,
            created_ip=None,
            user_agent=None,
        )


def test_internal_token_accepts_aware() -> None:
    InternalToken(
        id=uuid4(),
        user_id=None,
        purpose="password_reset",
        token_hash="h",
        expires_at=_AWARE,
        used_at=None,
        created_at=_AWARE,
        created_ip=None,
    )


def test_audit_event_rejects_naive() -> None:
    with pytest.raises(ValueError, match="AuditEvent.created_at"):
        AuditEvent(
            id=uuid4(),
            user_id=None,
            event_type="auth.login",
            metadata={},
            created_at=_NAIVE,
            ip_address=None,
            user_agent=None,
        )
