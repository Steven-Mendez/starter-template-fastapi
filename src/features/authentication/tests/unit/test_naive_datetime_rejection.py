"""Auth domain models reject naive datetimes at construction."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from features.authentication.domain.models import (
    AuditEvent,
    InternalToken,
    RefreshToken,
)

pytestmark = pytest.mark.unit


_AWARE = datetime(2026, 1, 1, tzinfo=timezone.utc)
_NAIVE = datetime(2026, 1, 1)


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
