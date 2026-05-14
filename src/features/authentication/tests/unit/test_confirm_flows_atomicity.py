"""Regression coverage for the confirm-flow Unit-of-Work refactor.

The fakes used by these tests snapshot their dict-backed stores on
``register_user_transaction`` / ``internal_token_transaction`` entry
and restore them on exception, mirroring how the real SQLModel
adapter rolls a transaction back. The behavioral expectations are
unchanged: a crash anywhere in the chain must roll back every
sibling write.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from features.authentication.application.crypto import (
    PasswordService,
    hash_token,
)
from features.authentication.application.use_cases.auth.confirm_email_verification import (  # noqa: E501
    EMAIL_VERIFY_PURPOSE,
    ConfirmEmailVerification,
)
from features.authentication.application.use_cases.auth.confirm_password_reset import (
    PASSWORD_RESET_PURPOSE,
    ConfirmPasswordReset,
)
from features.authentication.application.use_cases.auth.register_user import (
    RegisterUser,
)
from features.authentication.tests.fakes import FakeAuthRepository
from features.users.tests.fakes.fake_user_port import FakeUserPort

pytestmark = pytest.mark.unit

PASSWORD = "OriginalPass123!"
NEW_PASSWORD = "BrandNewPass987!"


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        environment="test",
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
    )


@pytest.fixture
def users() -> FakeUserPort:
    return FakeUserPort()


@pytest.fixture
def repository(users: FakeUserPort) -> FakeAuthRepository:
    repo = FakeAuthRepository()
    repo.attach_user_writer(users)
    return repo


@pytest.fixture
def password_service() -> PasswordService:
    return PasswordService()


def _register(
    repository: FakeAuthRepository, password_service: PasswordService, email: str
) -> UUID:
    register = RegisterUser(
        _repository=repository,
        _password_service=password_service,
    )
    result = register.execute(email=email, password=PASSWORD)
    assert isinstance(result, Ok)
    return result.value.id


def _seed_password_reset_token(
    repository: FakeAuthRepository, user_id: UUID, *, token: str
) -> None:
    repository.create_internal_token(
        user_id=user_id,
        purpose=PASSWORD_RESET_PURPOSE,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_ip=None,
    )


def _seed_email_verify_token(
    repository: FakeAuthRepository, user_id: UUID, *, token: str
) -> None:
    repository.create_internal_token(
        user_id=user_id,
        purpose=EMAIL_VERIFY_PURPOSE,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_ip=None,
    )


def test_confirm_password_reset_rolls_back_when_token_consumption_fails(
    repository: FakeAuthRepository,
    password_service: PasswordService,
) -> None:
    user_id = _register(repository, password_service, "reset-rollback@example.com")
    original_credential = repository.get_credential_for_user(user_id)
    assert original_credential is not None

    token = "raw-reset-token"
    _seed_password_reset_token(repository, user_id, token=token)

    # Stash a refresh token so we can prove the revoke also rolls back.
    refresh = repository.create_refresh_token(
        user_id=user_id,
        token_hash="refresh-hash-1",
        family_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=7),
        created_ip=None,
        user_agent=None,
    )

    class _ExplodingRepository(FakeAuthRepository):
        """Wraps the fake so ``mark_internal_token_used`` raises in-tx."""

        def __init__(self, inner: FakeAuthRepository) -> None:
            super().__init__()
            self._s = inner._s
            self._user_writer = inner._user_writer

        def mark_internal_token_used(self, token_id: UUID) -> None:
            raise RuntimeError("token-consumption write failed mid-confirm")

    exploding = _ExplodingRepository(repository)
    use_case = ConfirmPasswordReset(
        _repository=exploding,
        _password_service=password_service,
    )

    with pytest.raises(RuntimeError, match="token-consumption write failed"):
        use_case.execute(token=token, new_password=NEW_PASSWORD)

    # Credential unchanged: the rollback restored the original hash.
    after = repository.get_credential_for_user(user_id)
    assert after is not None
    assert after.hash == original_credential.hash
    # The reset token is still unconsumed.
    token_row = repository.get_internal_token(
        token_hash=hash_token(token), purpose=PASSWORD_RESET_PURPOSE
    )
    assert token_row is not None
    assert token_row.used_at is None
    # The refresh token is still live (revocation rolled back).
    surviving = repository.get_refresh_token_by_hash(refresh.token_hash)
    assert surviving is not None
    assert surviving.revoked_at is None


def test_confirm_email_verification_rolls_back_when_audit_write_fails(
    repository: FakeAuthRepository,
    password_service: PasswordService,
    users: FakeUserPort,
) -> None:
    """A crash on the audit write must roll back the verified flag and token."""
    user_id = _register(repository, password_service, "verify-rollback@example.com")
    assert users.stored_users[user_id].is_verified is False

    token = "raw-verify-token"
    _seed_email_verify_token(repository, user_id, token=token)

    class _ExplodingRepository(FakeAuthRepository):
        def __init__(self, inner: FakeAuthRepository) -> None:
            super().__init__()
            self._s = inner._s
            self._user_writer = inner._user_writer

        def record_audit_event(
            self,
            *,
            event_type: str,
            user_id: UUID | None = None,
            ip_address: str | None = None,
            user_agent: str | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            # Allow registration's audit write to land; only crash on
            # the email-verification audit so the verified-flag and
            # token-consumption rollback path is the only thing under
            # test. The registration audit event is recorded earlier
            # in setup so this guard only fires inside the confirm
            # transaction.
            if event_type == "auth.email_verified":
                raise RuntimeError("audit write failed mid-confirm")
            return super().record_audit_event(
                event_type=event_type,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata,
            )

    exploding = _ExplodingRepository(repository)
    use_case = ConfirmEmailVerification(_repository=exploding)

    with pytest.raises(RuntimeError, match="audit write failed"):
        use_case.execute(token=token)

    # Verified flag rolled back.
    assert users.stored_users[user_id].is_verified is False
    # Token still unconsumed.
    token_row = repository.get_internal_token(
        token_hash=hash_token(token), purpose=EMAIL_VERIFY_PURPOSE
    )
    assert token_row is not None
    assert token_row.used_at is None


def test_confirm_password_reset_happy_path_commits_everything(
    repository: FakeAuthRepository,
    password_service: PasswordService,
) -> None:
    user_id = _register(repository, password_service, "reset-happy@example.com")
    original = repository.get_credential_for_user(user_id)
    assert original is not None

    token = "happy-reset-token"
    _seed_password_reset_token(repository, user_id, token=token)

    use_case = ConfirmPasswordReset(
        _repository=repository,
        _password_service=password_service,
    )
    result = use_case.execute(token=token, new_password=NEW_PASSWORD)
    assert isinstance(result, Ok)

    # New credential committed; token consumed; audit event recorded.
    updated = repository.get_credential_for_user(user_id)
    assert updated is not None
    assert updated.hash != original.hash
    token_row = repository.get_internal_token(
        token_hash=hash_token(token), purpose=PASSWORD_RESET_PURPOSE
    )
    assert token_row is not None
    assert token_row.used_at is not None
    audit_events = [
        e
        for e in repository.stored_audit_events
        if e.event_type == "auth.password_reset_completed" and e.user_id == user_id
    ]
    assert len(audit_events) == 1


def test_confirm_email_verification_happy_path_marks_user_verified(
    repository: FakeAuthRepository,
    password_service: PasswordService,
    users: FakeUserPort,
) -> None:
    user_id = _register(repository, password_service, "verify-happy@example.com")
    assert users.stored_users[user_id].is_verified is False

    token = "happy-verify-token"
    _seed_email_verify_token(repository, user_id, token=token)

    use_case = ConfirmEmailVerification(_repository=repository)
    result = use_case.execute(token=token)
    assert isinstance(result, Ok)
    assert users.stored_users[user_id].is_verified is True
    audit_events = [
        e
        for e in repository.stored_audit_events
        if e.event_type == "auth.email_verified" and e.user_id == user_id
    ]
    assert len(audit_events) == 1


def test_confirm_email_verification_token_already_used_returns_err(
    repository: FakeAuthRepository,
    password_service: PasswordService,
) -> None:
    user_id = _register(repository, password_service, "verify-twice@example.com")
    token = "twice-verify-token"
    _seed_email_verify_token(repository, user_id, token=token)

    use_case = ConfirmEmailVerification(_repository=repository)
    first = use_case.execute(token=token)
    assert isinstance(first, Ok)

    second = use_case.execute(token=token)
    assert isinstance(second, Err)
