"""Unit tests for the ``RegisterUser`` use case."""

from __future__ import annotations

import pytest

from src.features.authentication.application.crypto import PasswordService
from src.features.authentication.application.errors import DuplicateEmailError
from src.features.authentication.application.use_cases.auth.register_user import (
    RegisterUser,
)
from src.features.authentication.tests.fakes import FakeAuthRepository
from src.platform.config.settings import AppSettings
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


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
def use_case(repository: FakeAuthRepository, settings: AppSettings) -> RegisterUser:
    return RegisterUser(
        _repository=repository,
        _password_service=PasswordService(),
        _settings=settings,
    )


def test_register_user_succeeds_when_email_is_new(
    use_case: RegisterUser, repository: FakeAuthRepository
) -> None:
    result = use_case.execute(email="new@example.com", password="StrongPass123!")

    assert isinstance(result, Ok)
    user = result.value
    assert user.email == "new@example.com"
    assert user.id in repository.stored_users


def test_register_user_returns_err_on_duplicate_email(
    use_case: RegisterUser,
) -> None:
    first = use_case.execute(email="dup@example.com", password="StrongPass123!")
    assert isinstance(first, Ok)

    second = use_case.execute(email="dup@example.com", password="DifferentPass99!")

    assert isinstance(second, Err)
    assert isinstance(second.error, DuplicateEmailError)


def test_register_user_stores_password_as_hash_not_plaintext(
    use_case: RegisterUser, repository: FakeAuthRepository
) -> None:
    raw_password = "PlainTextPass123!"

    result = use_case.execute(email="hash@example.com", password=raw_password)

    assert isinstance(result, Ok)
    stored = repository.stored_users[result.value.id]
    assert stored.password_hash != raw_password
    assert stored.password_hash.startswith("$argon2")
