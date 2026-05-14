"""Unit tests for the ``RegisterUser`` use case."""

from __future__ import annotations

from uuid import UUID

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from features.authentication.application.crypto import PasswordService
from features.authentication.application.errors import DuplicateEmailError
from features.authentication.application.use_cases.auth.register_user import (
    RegisterUser,
)
from features.authentication.domain.models import Credential
from features.authentication.tests.fakes import FakeAuthRepository
from features.users.tests.fakes.fake_user_port import FakeUserPort

pytestmark = pytest.mark.unit


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
def use_case(repository: FakeAuthRepository) -> RegisterUser:
    return RegisterUser(
        _repository=repository,
        _password_service=PasswordService(),
    )


def test_register_user_succeeds_when_email_is_new(
    use_case: RegisterUser, users: FakeUserPort
) -> None:
    result = use_case.execute(email="new@example.com", password="StrongPass123!")

    assert isinstance(result, Ok)
    user = result.value
    assert user.email == "new@example.com"
    assert user.id in users.stored_users


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
    credential = repository.get_credential_for_user(result.value.id)
    assert credential is not None
    assert credential.algorithm == "argon2"
    assert credential.hash != raw_password
    assert credential.hash.startswith("$argon2")


def test_register_user_rolls_back_user_row_when_credential_write_fails(
    repository: FakeAuthRepository, users: FakeUserPort
) -> None:
    """A crash in ``upsert_credential`` must roll back the user row.

    Regression coverage for the atomicity requirement: registration
    runs all three writes inside one transaction, so a failure on
    the credential write leaves the database in the pre-registration
    state — no ``User`` row, no audit event, and the email remains
    usable on a retry.
    """

    class _ExplodingTxRepository(FakeAuthRepository):
        """Fake whose registration transaction raises on credential upsert."""

        def __init__(self, inner: FakeAuthRepository) -> None:
            super().__init__()
            self._s = inner._s
            self._user_writer = inner._user_writer

        def upsert_credential(
            self, *, user_id: UUID, algorithm: str, hash: str
        ) -> Credential:
            raise RuntimeError("credential write failed mid-registration")

    exploding = _ExplodingTxRepository(repository)
    use_case = RegisterUser(
        _repository=exploding,
        _password_service=PasswordService(),
    )

    with pytest.raises(RuntimeError, match="credential write failed"):
        use_case.execute(email="rollback@example.com", password="StrongPass123!")

    # The user row was rolled back: a fresh ``get_by_email`` returns
    # ``None`` and the email is free for a retry. This is the
    # property the spec calls out (no ``UserPort.get_by_email`` hit
    # afterwards finding the user).
    assert users.get_by_email("rollback@example.com") is None
    # And no audit event survived.
    assert repository.stored_audit_events == []
