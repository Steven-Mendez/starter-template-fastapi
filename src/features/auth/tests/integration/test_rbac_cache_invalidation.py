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
from src.platform.shared.result import Ok

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
    container.seed_initial_data.execute()
    reg = container.register_user.execute(
        email="cache-test@example.com", password="UserPassword123!"
    )
    assert isinstance(reg, Ok)
    user = reg.value

    role = container.repository.get_role_by_name("user")
    assert role is not None

    login = container.login_user.execute(
        email="cache-test@example.com", password="UserPassword123!"
    )
    assert isinstance(login, Ok)
    tokens, principal = login.value
    access_token = tokens.access_token

    resolve = container.resolve_principal.execute(access_token)
    assert isinstance(resolve, Ok)
    assert "user" in resolve.value.roles

    container.remove_user_role.execute(
        actor=principal, user_id=user.id, role_id=role.id
    )

    from src.platform.shared.result import Err

    result = container.resolve_principal.execute(access_token)
    assert isinstance(result, Err)
    assert isinstance(result.error, StaleTokenError)


def test_assign_user_role_evicts_principal_cache(container: AuthContainer) -> None:
    container.seed_initial_data.execute()
    reg = container.register_user.execute(
        email="cache-assign@example.com", password="UserPassword123!"
    )
    assert isinstance(reg, Ok)

    role = container.repository.get_role_by_name("manager")
    assert role is not None

    login = container.login_user.execute(
        email="cache-assign@example.com", password="UserPassword123!"
    )
    assert isinstance(login, Ok)
    tokens, principal = login.value
    access_token = tokens.access_token

    container.resolve_principal.execute(access_token)

    container.assign_user_role.execute(
        actor=principal, user_id=principal.user_id, role_id=role.id
    )

    from src.platform.shared.result import Err

    result = container.resolve_principal.execute(access_token)
    assert isinstance(result, Err)
    assert isinstance(result.error, StaleTokenError)
