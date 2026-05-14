"""Unit tests for the ``RotateRefreshToken`` use case."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from features.authentication.application.crypto import PasswordService, hash_token
from features.authentication.application.errors import InvalidTokenError
from features.authentication.application.jwt_tokens import AccessTokenService
from features.authentication.application.use_cases.auth.login_user import LoginUser
from features.authentication.application.use_cases.auth.refresh_token import (
    RotateRefreshToken,
)
from features.authentication.application.use_cases.auth.register_user import (
    RegisterUser,
)
from features.authentication.tests.fakes import FakeAuthRepository
from features.users.tests.fakes.fake_user_port import FakeUserPort

pytestmark = pytest.mark.unit

PASSWORD = "StrongPass123!"
EMAIL = "refresh@example.com"


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


@pytest.fixture
def issued_refresh_token(
    users: FakeUserPort,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    settings: AppSettings,
) -> str:
    """Register and log in a user; return the raw refresh token."""
    register = RegisterUser(
        _repository=repository,
        _password_service=password_service,
    )
    register.execute(email=EMAIL, password=PASSWORD)

    login = LoginUser(
        _users=users,
        _repository=repository,
        _password_service=password_service,
        _token_service=AccessTokenService(settings),
        _settings=settings,
        _dummy_hash=password_service.hash_password("dummy-password"),
    )
    result = login.execute(email=EMAIL, password=PASSWORD)
    assert isinstance(result, Ok)
    return result.value[0].refresh_token


@pytest.fixture
def rotate(
    users: FakeUserPort,
    repository: FakeAuthRepository,
    settings: AppSettings,
) -> RotateRefreshToken:
    return RotateRefreshToken(
        _users=users,
        _repository=repository,
        _token_service=AccessTokenService(settings),
        _settings=settings,
    )


def test_rotate_refresh_token_success_marks_old_rotated(
    rotate: RotateRefreshToken,
    repository: FakeAuthRepository,
    issued_refresh_token: str,
) -> None:
    original_hash = hash_token(issued_refresh_token)
    original = repository.get_refresh_token_by_hash(original_hash)
    assert original is not None
    assert original.revoked_at is None

    result = rotate.execute(refresh_token=issued_refresh_token)

    assert isinstance(result, Ok)
    tokens, _ = result.value
    assert tokens.refresh_token != issued_refresh_token
    after = repository.get_refresh_token_by_hash(original_hash)
    assert after is not None
    assert after.revoked_at is not None


def test_reusing_revoked_token_revokes_entire_family(
    rotate: RotateRefreshToken,
    repository: FakeAuthRepository,
    issued_refresh_token: str,
) -> None:
    first = rotate.execute(refresh_token=issued_refresh_token)
    assert isinstance(first, Ok)

    # Reusing the original (now-rotated) token should revoke the whole family.
    reuse = rotate.execute(refresh_token=issued_refresh_token)

    assert isinstance(reuse, Err)
    assert isinstance(reuse.error, InvalidTokenError)
    family_id = repository.get_refresh_token_by_hash(hash_token(issued_refresh_token))
    assert family_id is not None
    family_tokens = [
        t
        for t in repository.stored_refresh_tokens.values()
        if t.family_id == family_id.family_id
    ]
    assert family_tokens, "expected at least one token in the family"
    assert all(t.revoked_at is not None for t in family_tokens)


def test_expired_refresh_token_returns_invalid_token_error(
    rotate: RotateRefreshToken,
    users: FakeUserPort,
    repository: FakeAuthRepository,
) -> None:
    user_result = users.create(email="exp@example.com")
    assert isinstance(user_result, Ok)
    user = user_result.value
    raw = "expired-refresh-token"
    repository.create_refresh_token(
        user_id=user.id,
        token_hash=hash_token(raw),
        family_id=uuid4(),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        created_ip=None,
        user_agent=None,
    )

    result = rotate.execute(refresh_token=raw)

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidTokenError)
