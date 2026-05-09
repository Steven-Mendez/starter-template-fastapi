"""Refresh-token families must never span more than one user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)

pytestmark = pytest.mark.integration


def test_create_refresh_token_rejects_family_belonging_to_other_user(
    sqlite_auth_repository: SQLModelAuthRepository,
) -> None:
    repo = sqlite_auth_repository
    user_a = repo.create_user(email="a@example.com", password_hash="hash-a")
    user_b = repo.create_user(email="b@example.com", password_hash="hash-b")
    assert user_a is not None and user_b is not None

    family_id = uuid4()
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    repo.create_refresh_token(
        user_id=user_a.id,
        token_hash="hash-token-a",
        family_id=family_id,
        expires_at=expires,
        created_ip=None,
        user_agent=None,
    )

    with pytest.raises(ValueError, match="different user"):
        repo.create_refresh_token(
            user_id=user_b.id,
            token_hash="hash-token-b",
            family_id=family_id,
            expires_at=expires,
            created_ip=None,
            user_agent=None,
        )
