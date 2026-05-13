"""Unit tests for the ``LoginUser`` use case."""

from __future__ import annotations

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from features.authentication.application.crypto import PasswordService
from features.authentication.application.errors import (
    InactiveUserError,
    InvalidCredentialsError,
)
from features.authentication.application.jwt_tokens import AccessTokenService
from features.authentication.application.use_cases.auth.login_user import LoginUser
from features.authentication.application.use_cases.auth.register_user import (
    RegisterUser,
)
from features.authentication.tests.fakes import FakeAuthRepository
from features.users.tests.fakes.fake_user_port import FakeUserPort

pytestmark = pytest.mark.unit

PASSWORD = "StrongPass123!"


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        environment="test",
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
    )


@pytest.fixture
def repository() -> FakeAuthRepository:
    return FakeAuthRepository()


@pytest.fixture
def users() -> FakeUserPort:
    return FakeUserPort()


@pytest.fixture
def password_service() -> PasswordService:
    return PasswordService()


@pytest.fixture
def login_use_case(
    users: FakeUserPort,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    settings: AppSettings,
) -> LoginUser:
    return LoginUser(
        _users=users,
        _repository=repository,
        _password_service=password_service,
        _token_service=AccessTokenService(settings),
        _settings=settings,
        _dummy_hash=password_service.hash_password("dummy-password"),
    )


@pytest.fixture
def register_use_case(
    users: FakeUserPort,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    settings: AppSettings,
) -> RegisterUser:
    return RegisterUser(
        _users=users,
        _credentials=repository,
        _audit=repository,
        _password_service=password_service,
        _settings=settings,
    )


def test_login_succeeds_with_valid_credentials(
    login_use_case: LoginUser, register_use_case: RegisterUser
) -> None:
    register_use_case.execute(email="ok@example.com", password=PASSWORD)

    result = login_use_case.execute(email="ok@example.com", password=PASSWORD)

    assert isinstance(result, Ok)
    tokens, principal = result.value
    assert tokens.access_token
    assert tokens.refresh_token
    assert principal.email == "ok@example.com"


def test_login_with_wrong_password_returns_invalid_credentials(
    login_use_case: LoginUser, register_use_case: RegisterUser
) -> None:
    register_use_case.execute(email="wrongpw@example.com", password=PASSWORD)

    result = login_use_case.execute(email="wrongpw@example.com", password="WrongPass!1")

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidCredentialsError)


def test_login_with_unknown_email_returns_invalid_credentials_and_runs_dummy_verify(
    login_use_case: LoginUser, password_service: PasswordService
) -> None:
    verify_calls: list[tuple[str, str]] = []
    original_verify = password_service.verify_password

    def spy(password_hash: str, password: str) -> bool:
        verify_calls.append((password_hash, password))
        return original_verify(password_hash, password)

    password_service.verify_password = spy  # type: ignore[method-assign]

    result = login_use_case.execute(email="ghost@example.com", password="AnyPass123!")

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidCredentialsError)
    # The dummy hash path was invoked to keep timing parity with the
    # wrong-password branch (no user-existence enumeration).
    assert any(
        call_password == "AnyPass123!" and call_hash == login_use_case._dummy_hash
        for call_hash, call_password in verify_calls
    )


def test_login_for_inactive_user_returns_inactive_user_error(
    login_use_case: LoginUser,
    register_use_case: RegisterUser,
    users: FakeUserPort,
) -> None:
    reg = register_use_case.execute(email="inactive@example.com", password=PASSWORD)
    assert isinstance(reg, Ok)
    users.set_active(reg.value.id, is_active=False)

    result = login_use_case.execute(email="inactive@example.com", password=PASSWORD)

    assert isinstance(result, Err)
    assert isinstance(result.error, InactiveUserError)
