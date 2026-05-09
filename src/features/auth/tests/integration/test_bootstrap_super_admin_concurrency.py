"""Concurrency test for bootstrap_super_admin.

Two threads racing to bootstrap the same super-admin should produce exactly
one user row, not two, and that user should have the super_admin role.
The fix catches DuplicateEmailError and retries the get_user_by_email lookup
so the loser falls through cleanly instead of propagating the conflict.
"""

from __future__ import annotations

import threading

import pytest

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.auth.composition.container import build_auth_container
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.integration


def test_concurrent_bootstrap_creates_exactly_one_super_admin(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
    _auth_postgres_url: str,
) -> None:
    # ``postgres_auth_repository`` is requested only to clear the database and
    # ensure the schema exists; threads create their own pools from the raw URL.
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_redis_url": None,
        }
    )

    errors: list[Exception] = []
    results: list[object] = []
    lock = threading.Lock()

    def run_bootstrap() -> None:
        # Each replica creates its own connection pool, matching real deployments.
        repo = SQLModelAuthRepository(_auth_postgres_url, create_schema=True)
        container = build_auth_container(settings=settings, repository=repo)
        try:
            user = container.rbac_service.bootstrap_super_admin(
                auth_service=container.auth_service,
                email="concurrent-admin@example.com",
                password="StrongPassword123!",
            )
            with lock:
                results.append(user)
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            container.shutdown()

    t1 = threading.Thread(target=run_bootstrap, name="bootstrap-1")
    t2 = threading.Thread(target=run_bootstrap, name="bootstrap-2")
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    assert not errors, f"Bootstrap raised unexpected errors: {errors}"
    assert len(results) == 2, "Both threads should return a result"

    # Both should return the same user (by email).
    emails = {getattr(r, "email", None) for r in results}
    assert emails == {"concurrent-admin@example.com"}

    # The user must exist exactly once in the database and hold the super_admin role.
    verification_repo = SQLModelAuthRepository(_auth_postgres_url, create_schema=False)
    try:
        user = verification_repo.get_user_by_email("concurrent-admin@example.com")
        assert user is not None
        principal = verification_repo.get_principal(user.id)
        assert principal is not None
        assert "super_admin" in principal.roles
    finally:
        verification_repo.close()
