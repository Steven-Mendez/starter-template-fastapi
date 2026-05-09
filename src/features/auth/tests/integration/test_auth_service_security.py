"""Security-focused tests for auth service behavior."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import pytest

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.auth.application.errors import (
    EmailNotVerifiedError,
    PermissionDeniedError,
)
from src.features.auth.application.services import RBACService, ensure_permissions
from src.features.auth.application.types import Principal
from src.features.auth.composition.container import build_auth_container
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.integration


class _RecordingCache:
    def __init__(self) -> None:
        self.invalidated: list[UUID] = []

    def get(self, token_id: str) -> Principal | None:
        del token_id
        return None

    def set(self, token_id: str, principal: Principal) -> None:
        del token_id, principal

    def pop(self, token_id: str) -> None:
        del token_id

    def invalidate_user(self, user_id: UUID) -> None:
        self.invalidated.append(user_id)

    def close(self) -> None:
        pass


def _actor() -> Principal:
    return Principal(
        user_id=uuid4(),
        email="admin@example.com",
        is_active=True,
        is_verified=True,
        authz_version=1,
        roles=frozenset({"super_admin"}),
        permissions=frozenset({"users:roles:manage"}),
    )


def test_service_normalizes_email_for_register_and_login(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
) -> None:
    container = build_auth_container(
        settings=test_settings, repository=sqlite_auth_repository
    )

    user = container.auth_service.register(
        email="User@Example.COM",
        password="UserPassword123!",
    )
    _, principal = container.auth_service.login(
        email="user@example.com",
        password="UserPassword123!",
    )

    assert user.email == "user@example.com"
    assert principal.email == "user@example.com"
    container.shutdown()


def test_service_blocks_unverified_login_when_required(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
) -> None:
    settings = test_settings.model_copy(
        update={"auth_require_email_verification": True}
    )
    container = build_auth_container(
        settings=settings, repository=sqlite_auth_repository
    )
    container.auth_service.register(
        email="unverified@example.com",
        password="UserPassword123!",
    )

    with pytest.raises(EmailNotVerifiedError):
        container.auth_service.login(
            email="UNVERIFIED@example.com",
            password="UserPassword123!",
        )

    container.shutdown()


def test_role_revocation_invalidates_principal_cache(
    sqlite_auth_repository: SQLModelAuthRepository,
) -> None:
    user = sqlite_auth_repository.create_user(
        email="cache-target@example.com", password_hash="hash"
    )
    role = sqlite_auth_repository.create_role(name="cache_role")
    assert user is not None
    assert role is not None
    sqlite_auth_repository.assign_user_role(user.id, role.id)
    cache = _RecordingCache()
    service = RBACService(repository=sqlite_auth_repository, cache=cache)

    service.remove_user_role(
        actor=_actor(),
        user_id=user.id,
        role_id=role.id,
    )

    assert cache.invalidated == [user.id]


def test_permission_denial_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    principal = _actor()
    caplog.set_level(logging.WARNING, logger="src.features.auth.application.services")

    with pytest.raises(PermissionDeniedError):
        ensure_permissions(principal, {"reports:read"}, any_=False)

    assert "event=rbac.permission_denied" in caplog.text
    assert str(principal.user_id) in caplog.text
    assert "required_permission" in caplog.text
