"""Unit tests pinning the timing-parity invariants in ``LoginUser``.

Login must issue exactly one ``get_credential_for_user`` call and exactly
one ``verify_password`` call regardless of whether the email maps to a
user — otherwise an attacker can enumerate registered emails through
wall-clock measurement of the response time.
"""

from __future__ import annotations

from typing import Any

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from features.authentication.application.crypto import (
    FIXED_DUMMY_ARGON2_HASH,
    PasswordService,
)
from features.authentication.application.errors import InvalidCredentialsError
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
    )


@pytest.fixture
def register_use_case(
    repository: FakeAuthRepository,
    password_service: PasswordService,
) -> RegisterUser:
    return RegisterUser(
        _repository=repository,
        _password_service=password_service,
    )


def _wrap_credential_lookup(
    login_use_case: LoginUser,
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Any, ...]]:
    """Spy on the use case's single credential-lookup call site.

    The implementation routes both branches through
    ``LoginUser._get_credential_for_user`` (a thin wrapper that
    short-circuits to ``None`` for the ``_NoCredentialUserId`` sentinel).
    The parity guarantee is "exactly one invocation of this method per
    request, regardless of whether the email maps to a user" — so the
    DB-roundtrip-count timing channel is closed at the call-site level.

    ``LoginUser`` is a ``slots=True`` dataclass, so we patch the method
    at the class level via ``monkeypatch.setattr`` rather than rebinding
    on the instance (the latter would raise ``AttributeError`` due to
    the slot layout).
    """
    calls: list[tuple[Any, ...]] = []
    original = LoginUser._get_credential_for_user

    def spy(self: LoginUser, user_id: Any) -> Any:
        calls.append((user_id,))
        return original(self, user_id)

    monkeypatch.setattr(LoginUser, "_get_credential_for_user", spy)
    return calls


def _wrap_verify_password(
    password_service: PasswordService,
) -> list[tuple[str, str]]:
    """Spy on ``verify_password`` and return a recorded-calls list."""
    calls: list[tuple[str, str]] = []
    original = password_service.verify_password

    def spy(password_hash: str, password: str) -> bool:
        calls.append((password_hash, password))
        return original(password_hash, password)

    password_service.verify_password = spy  # type: ignore[method-assign]
    return calls


def test_login_hit_branch_invokes_credential_lookup_and_verify_exactly_once(
    login_use_case: LoginUser,
    register_use_case: RegisterUser,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hit branch (known email): exactly one credential lookup, one verify."""
    register_use_case.execute(email="known@example.com", password=PASSWORD)

    credential_calls = _wrap_credential_lookup(login_use_case, monkeypatch)
    verify_calls = _wrap_verify_password(password_service)

    result = login_use_case.execute(email="known@example.com", password=PASSWORD)

    assert isinstance(result, Ok)
    assert len(credential_calls) == 1, (
        f"Expected exactly one credential-lookup call on the hit branch, "
        f"got {len(credential_calls)}: {credential_calls!r}"
    )
    assert len(verify_calls) == 1, (
        f"Expected exactly one verify_password call on the hit branch, "
        f"got {len(verify_calls)}: {verify_calls!r}"
    )
    # The verify is against the stored credential hash, not the dummy.
    assert verify_calls[0][0] != FIXED_DUMMY_ARGON2_HASH
    assert verify_calls[0][1] == PASSWORD


def test_login_miss_branch_invokes_credential_lookup_and_verify_exactly_once(
    login_use_case: LoginUser,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Miss branch (unknown email): exactly one credential lookup, one verify.

    The DB-roundtrip count and Argon2 verify count must match the hit
    branch so the timing channel that would otherwise let an attacker
    enumerate registered emails is closed.
    """
    credential_calls = _wrap_credential_lookup(login_use_case, monkeypatch)
    verify_calls = _wrap_verify_password(password_service)

    result = login_use_case.execute(email="ghost@example.com", password="AnyPass123!")

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidCredentialsError)
    assert len(credential_calls) == 1, (
        f"Expected exactly one credential-lookup call on the miss branch "
        f"(parity with hit branch), got {len(credential_calls)}: "
        f"{credential_calls!r}"
    )
    assert len(verify_calls) == 1, (
        f"Expected exactly one verify_password call on the miss branch "
        f"(parity with hit branch), got {len(verify_calls)}: {verify_calls!r}"
    )
    # The verify is against the module-level fixed dummy hash.
    assert verify_calls[0][0] == FIXED_DUMMY_ARGON2_HASH
    assert verify_calls[0][1] == "AnyPass123!"


def test_login_hit_and_miss_have_equal_call_counts(
    login_use_case: LoginUser,
    register_use_case: RegisterUser,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hit and miss branches must produce identical (credential, verify) counts.

    This is the parity assertion stated in tasks.md 1.4. Counts are the
    observable that drives the timing channel; both must match.
    """
    register_use_case.execute(email="known@example.com", password=PASSWORD)

    credential_calls = _wrap_credential_lookup(login_use_case, monkeypatch)
    verify_calls = _wrap_verify_password(password_service)

    login_use_case.execute(email="known@example.com", password=PASSWORD)
    hit_credential = len(credential_calls)
    hit_verify = len(verify_calls)

    login_use_case.execute(email="ghost@example.com", password=PASSWORD)
    miss_credential = len(credential_calls) - hit_credential
    miss_verify = len(verify_calls) - hit_verify

    assert hit_credential == miss_credential == 1
    assert hit_verify == miss_verify == 1
