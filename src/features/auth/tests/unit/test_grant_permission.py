"""Unit tests for the ``AssignRolePermission`` use case."""

from __future__ import annotations

from uuid import UUID

import pytest

from src.features.auth.application.use_cases.rbac.assign_role_permission import (
    AssignRolePermission,
)
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
def grant_permission(repository: FakeAuthRepository) -> AssignRolePermission:
    return AssignRolePermission(_repository=repository, _cache=None)


@pytest.fixture
def assign_role(repository: FakeAuthRepository) -> AssignUserRole:
    return AssignUserRole(_repository=repository, _cache=None)


def _actor() -> Principal:
    return Principal(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        email="admin@example.com",
        is_active=True,
        is_verified=True,
        authz_version=1,
        roles=frozenset({"super_admin"}),
        permissions=frozenset({"permissions:manage"}),
    )


def test_grant_permission_bumps_authz_version_for_all_role_users(
    repository: FakeAuthRepository,
    grant_permission: AssignRolePermission,
    assign_role: AssignUserRole,
) -> None:
    role = repository.create_role(name="editor")
    permission = repository.create_permission(name="docs:write")
    assert role is not None and permission is not None

    user_a = repository.create_user(email="a@example.com", password_hash="x")
    user_b = repository.create_user(email="b@example.com", password_hash="x")
    assert user_a is not None and user_b is not None
    assign_role.execute(actor=_actor(), user_id=user_a.id, role_id=role.id)
    assign_role.execute(actor=_actor(), user_id=user_b.id, role_id=role.id)

    version_a_before = repository.stored_users[user_a.id].authz_version
    version_b_before = repository.stored_users[user_b.id].authz_version

    result = grant_permission.execute(
        actor=_actor(), role_id=role.id, permission_id=permission.id
    )

    assert isinstance(result, Ok)
    assert repository.stored_users[user_a.id].authz_version == version_a_before + 1
    assert repository.stored_users[user_b.id].authz_version == version_b_before + 1


def test_grant_permission_persists_assignment(
    repository: FakeAuthRepository,
    grant_permission: AssignRolePermission,
    assign_role: AssignUserRole,
) -> None:
    role = repository.create_role(name="viewer")
    permission = repository.create_permission(name="docs:read")
    assert role is not None and permission is not None

    user = repository.create_user(email="viewer@example.com", password_hash="x")
    assert user is not None
    assign_role.execute(actor=_actor(), user_id=user.id, role_id=role.id)

    grant_permission.execute(
        actor=_actor(), role_id=role.id, permission_id=permission.id
    )

    principal = repository.get_principal(user.id)
    assert principal is not None
    assert "docs:read" in principal.permissions
