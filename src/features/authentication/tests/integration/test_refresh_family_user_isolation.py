"""Refresh-token families must never span more than one user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.features.authentication.adapters.outbound.persistence.sqlmodel.repository import (  # noqa: E501
    SQLModelAuthRepository,
)
from src.features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from src.platform.shared.result import Ok

pytestmark = pytest.mark.integration


def test_create_refresh_token_rejects_family_belonging_to_other_user(
    sqlite_auth_repository: SQLModelAuthRepository,
    users_for_auth: SQLModelUserRepository,
) -> None:
    repo = sqlite_auth_repository
    user_a = users_for_auth.create(email="a@example.com")
    user_b = users_for_auth.create(email="b@example.com")
    assert isinstance(user_a, Ok)
    assert isinstance(user_b, Ok)

    family_id = uuid4()
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    repo.create_refresh_token(
        user_id=user_a.value.id,
        token_hash="hash-token-a",
        family_id=family_id,
        expires_at=expires,
        created_ip=None,
        user_agent=None,
    )

    with pytest.raises(ValueError, match="different user"):
        repo.create_refresh_token(
            user_id=user_b.value.id,
            token_hash="hash-token-b",
            family_id=family_id,
            expires_at=expires,
            created_ip=None,
            user_agent=None,
        )
