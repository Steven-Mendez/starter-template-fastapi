"""Integration tests verifying that RBAC mutations invalidate the principal cache.

When a role is added or removed, the principal cache entry for the affected user
must be evicted immediately so the next request re-reads from the DB rather than
serving a stale cached principal.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.auth.application.errors import StaleTokenError
from src.features.auth.composition.container import AuthContainer, build_auth_container
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.integration


@pytest.fixture
def container(
    test_settings: AppSettings,
    sqlite_auth_repository: SQLModelAuthRepository,
) -> Iterator[AuthContainer]:
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_redis_url": None,
            "auth_rate_limit_enabled": False,
            "auth_return_internal_tokens": True,
        }
    )
    c = build_auth_container(settings=settings, repository=sqlite_auth_repository)
    yield c
    c.shutdown()


def test_remove_user_role_evicts_principal_cache(container: AuthContainer) -> None:
    auth = container.auth_service
    rbac = container.rbac_service

    # Seed roles and create a user.
    rbac.seed_initial_data()
    user = auth.register(email="cache-test@example.com", password="UserPassword123!")

    role = container.repository.get_role_by_name("user")
    assert role is not None

    # Issue tokens and populate the principal cache.
    tokens, _ = auth.login(email="cache-test@example.com", password="UserPassword123!")
    access_token = tokens.access_token
    principal = auth.principal_from_access_token(access_token)
    assert "user" in principal.roles

    # Simulate an admin revoking the role. The cache must be evicted immediately.
    actor = principal
    rbac.remove_user_role(actor=actor, user_id=user.id, role_id=role.id)

    # The same token now carries a stale authz_version — must be rejected.
    with pytest.raises(StaleTokenError):
        auth.principal_from_access_token(access_token)


def test_assign_user_role_evicts_principal_cache(container: AuthContainer) -> None:
    auth = container.auth_service
    rbac = container.rbac_service

    rbac.seed_initial_data()
    auth.register(email="cache-assign@example.com", password="UserPassword123!")

    role = container.repository.get_role_by_name("manager")
    assert role is not None

    tokens, principal = auth.login(
        email="cache-assign@example.com", password="UserPassword123!"
    )
    access_token = tokens.access_token

    # Populate the cache.
    auth.principal_from_access_token(access_token)

    # Grant a new role — cache must be evicted.
    rbac.assign_user_role(actor=principal, user_id=principal.user_id, role_id=role.id)

    # The token carries the old authz_version — StaleTokenError expected.
    with pytest.raises(StaleTokenError):
        auth.principal_from_access_token(access_token)
