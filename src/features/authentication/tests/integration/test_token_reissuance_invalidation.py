"""Integration coverage for re-issuance invalidating prior unused tokens.

When a user requests a password-reset or email-verification token while a
prior one is still unused, the prior row(s) must be stamped
``used_at = now()`` in the same transaction as the new insert, so only
the latest issued token remains live. These tests exercise that
behaviour against a real PostgreSQL backend.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthInternalTokenTable,
)
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authentication.application.errors import TokenAlreadyUsedError
from features.authentication.composition.container import build_auth_container
from features.outbox.tests.fakes.fake_outbox import InlineDispatchOutboxUnitOfWork
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)

pytestmark = pytest.mark.integration


def _internal_token_rows(
    repo: SQLModelAuthRepository, *, purpose: str
) -> list[AuthInternalTokenTable]:
    """Return every internal-token row matching ``purpose``, oldest first."""
    with Session(repo.engine, expire_on_commit=False) as session:
        rows = session.exec(
            select(AuthInternalTokenTable)
            .where(AuthInternalTokenTable.purpose == purpose)
            .order_by(AuthInternalTokenTable.created_at)  # type: ignore[arg-type]
        ).all()
    return list(rows)


def test_third_password_reset_invalidates_prior_two(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_redis_url": None,
        }
    )
    users = SQLModelUserRepository(engine=postgres_auth_repository.engine)
    container = build_auth_container(
        settings=settings,
        users=users,
        outbox_uow=InlineDispatchOutboxUnitOfWork(dispatcher=lambda _n, _p: None),
        repository=postgres_auth_repository,
    )
    try:
        registration = container.register_user.execute(
            email="reset-reissue@example.com", password="UserPassword123!"
        )
        assert isinstance(registration, Ok)

        tokens: list[str] = []
        for _ in range(3):
            result = container.request_password_reset.execute(
                email="reset-reissue@example.com"
            )
            assert isinstance(result, Ok)
            assert result.value.token is not None
            tokens.append(result.value.token)

        rows = _internal_token_rows(postgres_auth_repository, purpose="password_reset")
        assert len(rows) == 3, "every request should still produce a row"
        # The first two rows (older) must be stamped used_at; only the
        # most recently issued row should be live.
        assert rows[0].used_at is not None
        assert rows[1].used_at is not None
        assert rows[2].used_at is None

        # Older tokens cannot be redeemed.
        for stale_token in tokens[:-1]:
            stale = container.confirm_password_reset.execute(
                token=stale_token, new_password="NewerPassword123!"
            )
            assert isinstance(stale, Err)
            assert isinstance(stale.error, TokenAlreadyUsedError)

        # The freshest token still works.
        live = container.confirm_password_reset.execute(
            token=tokens[-1], new_password="NewerPassword123!"
        )
        assert isinstance(live, Ok)
    finally:
        container.shutdown()


def test_third_email_verification_invalidates_prior_two(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_redis_url": None,
        }
    )
    users = SQLModelUserRepository(engine=postgres_auth_repository.engine)
    container = build_auth_container(
        settings=settings,
        users=users,
        outbox_uow=InlineDispatchOutboxUnitOfWork(dispatcher=lambda _n, _p: None),
        repository=postgres_auth_repository,
    )
    try:
        registration = container.register_user.execute(
            email="verify-reissue@example.com", password="UserPassword123!"
        )
        assert isinstance(registration, Ok)
        user = users.get_by_email("verify-reissue@example.com")
        assert user is not None

        tokens: list[str] = []
        for _ in range(3):
            result = container.request_email_verification.execute(user_id=user.id)
            assert isinstance(result, Ok)
            assert result.value.token is not None
            tokens.append(result.value.token)

        rows = _internal_token_rows(postgres_auth_repository, purpose="email_verify")
        assert len(rows) == 3
        assert rows[0].used_at is not None
        assert rows[1].used_at is not None
        assert rows[2].used_at is None

        # Older tokens cannot be redeemed.
        for stale_token in tokens[:-1]:
            stale = container.confirm_email_verification.execute(token=stale_token)
            assert isinstance(stale, Err)
            assert isinstance(stale.error, TokenAlreadyUsedError)

        # The freshest token still works.
        live = container.confirm_email_verification.execute(token=tokens[-1])
        assert isinstance(live, Ok)
    finally:
        container.shutdown()
