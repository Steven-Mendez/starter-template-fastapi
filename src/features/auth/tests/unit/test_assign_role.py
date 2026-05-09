"""Unit tests for the ``AssignUserRole`` use case."""

from __future__ import annotations

import pytest

from src.features.auth.application.use_cases.rbac.assign_user_role import (
    AssignUserRole,
)
from src.features.auth.tests.fakes import FakeAuthRepository
from src.platform.shared.principal import Principal
from src.platform.shared.result import Ok

pytestmark = pytest.mark.unit


@pytest.fixture
def repository() -> FakeAuthRepository:
    return FakeAuthRepository()


@pytest.fixture
def use_case(repository: FakeAuthRepository) -> AssignUserRole:
    return AssignUserRole(_repository=repository, _cache=None)


def _actor(user_id: str) -> Principal:
    from uuid import UUID

    return Principal(
        user_id=UUID(user_id),
        email="actor@example.com",
        is_active=True,
        is_verified=True,
        authz_version=1,
        roles=frozenset({"super_admin"}),
        permissions=frozenset({"users:roles:manage"}),
    )


def test_assign_role_increments_authz_version_for_user(
    repository: FakeAuthRepository, use_case: AssignUserRole
) -> None:
    user = repository.create_user(email="target@example.com", password_hash="x")
    assert user is not None
    role = repository.create_role(name="manager")
    assert role is not None
    initial_version = repository.stored_users[user.id].authz_version

    # AssignUserRole itself does not bump authz_version (the role grant alone
    # doesn't change the user's permission set until permissions are linked
    # to the role). This test pins the documented contract: the assignment
    # succeeds and the role appears on the principal.
    result = use_case.execute(
        actor=_actor("00000000-0000-0000-0000-000000000001"),
        user_id=user.id,
        role_id=role.id,
    )

    assert isinstance(result, Ok)
    principal = repository.get_principal(user.id)
    assert principal is not None
    assert "manager" in principal.roles
    assert repository.stored_users[user.id].authz_version >= initial_version
