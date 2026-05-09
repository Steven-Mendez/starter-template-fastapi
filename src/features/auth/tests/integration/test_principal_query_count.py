"""Regression test pinning the auth principal hydration to ≤ 2 queries.

The previous implementation issued three queries per request (user,
roles, permissions). This test instruments the SQLAlchemy engine with
``before_cursor_execute`` and fails if the count regresses, so a future
refactor that re-introduces the N+1 pattern is caught immediately.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def query_counter(
    sqlite_auth_repository: SQLModelAuthRepository,
) -> Iterator[list[int]]:
    """Return a single-element list whose value tracks executed-query count."""
    counter = [0]
    engine: Engine = sqlite_auth_repository.engine

    def _on_execute(*_args: Any, **_kwargs: Any) -> None:
        counter[0] += 1

    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


def test_get_principal_uses_at_most_two_queries(
    sqlite_auth_repository: SQLModelAuthRepository,
    query_counter: list[int],
) -> None:
    repo = sqlite_auth_repository
    user = repo.create_user(email="user@example.com", password_hash="hash")
    assert user is not None
    role = repo.create_role(name="manager")
    assert role is not None
    perm = repo.create_permission(name="users:read")
    assert perm is not None
    repo.assign_user_role(user.id, role.id)
    repo.assign_role_permission(role.id, perm.id)

    query_counter[0] = 0
    principal = repo.get_principal(user.id)

    assert principal is not None
    assert "manager" in principal.roles
    assert "users:read" in principal.permissions
    # 1 query for the user row + 1 for the role/permission join. Anything
    # higher means the N+1 pattern has crept back in.
    assert query_counter[0] <= 2, (
        f"Expected ≤ 2 queries to hydrate a principal; got {query_counter[0]}"
    )
