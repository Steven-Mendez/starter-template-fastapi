"""Unit tests pinning the timing-parity invariants in the token-issuance flows.

``RequestPasswordReset`` and ``RequestEmailVerification`` must invoke
``verify_password`` exactly once on both the known-email/known-user
branch and on the unknown branch — otherwise the unknown branch returns
sooner than the known branch and an attacker can enumerate registered
accounts through wall-clock timing.

Both branches call ``verify_password(FIXED_DUMMY_ARGON2_HASH, ...)``
exactly once. The known branch *also* runs the transactional audit +
token-write pipeline, but that pipeline's wall-clock (~7 ms) is small
relative to the Argon2 verify (~30-40 ms), so paying one Argon2-class
cost in both branches collapses the timing channel that would otherwise
be inverted (known-branch-fast vs unknown-branch-slow).

The "exactly once" assertion is the parity guarantee tasks.md 4.3
requires; it is the count we directly observe.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from features.authentication.application.crypto import (
    FIXED_DUMMY_ARGON2_HASH,
    PasswordService,
)
from features.authentication.application.errors import NotFoundError
from features.authentication.application.use_cases.auth.register_user import (
    RegisterUser,
)
from features.authentication.application.use_cases.auth.request_email_verification import (  # noqa: E501
    RequestEmailVerification,
)
from features.authentication.application.use_cases.auth.request_password_reset import (
    RequestPasswordReset,
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
        auth_return_internal_tokens=True,
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
def register_use_case(
    repository: FakeAuthRepository,
    password_service: PasswordService,
) -> RegisterUser:
    return RegisterUser(
        _repository=repository,
        _password_service=password_service,
    )


@pytest.fixture
def request_password_reset(
    users: FakeUserPort,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    settings: AppSettings,
) -> RequestPasswordReset:
    return RequestPasswordReset(
        _users=users,
        _repository=repository,
        _password_service=password_service,
        _settings=settings,
    )


@pytest.fixture
def request_email_verification(
    users: FakeUserPort,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    settings: AppSettings,
) -> RequestEmailVerification:
    return RequestEmailVerification(
        _users=users,
        _repository=repository,
        _password_service=password_service,
        _settings=settings,
    )


def _spy_verify(password_service: PasswordService) -> list[tuple[str, str]]:
    """Wrap ``verify_password`` and return a list that records each call."""
    calls: list[tuple[str, str]] = []
    original = password_service.verify_password

    def spy(password_hash: str, password: str) -> bool:
        calls.append((password_hash, password))
        return original(password_hash, password)

    password_service.verify_password = spy  # type: ignore[method-assign]
    return calls


# ── RequestPasswordReset ─────────────────────────────────────────────────────


def test_password_reset_unknown_email_calls_verify_exactly_once(
    request_password_reset: RequestPasswordReset,
    password_service: PasswordService,
) -> None:
    """Unknown-email branch: pays the Argon2 cost via one dummy-hash verify."""
    verify_calls = _spy_verify(password_service)

    result = request_password_reset.execute(email="ghost@example.com")

    # The use case still returns Ok (no-enumeration semantics: same shape
    # of response for known and unknown emails).
    assert isinstance(result, Ok)
    assert result.value.token is None
    assert len(verify_calls) == 1, (
        f"Expected exactly one verify_password call on the unknown-email "
        f"branch (timing parity with the known-email branch), got "
        f"{len(verify_calls)}: {verify_calls!r}"
    )
    assert verify_calls[0][0] == FIXED_DUMMY_ARGON2_HASH
    # ``email`` is passed as the candidate plaintext per the use case
    # contract; only the Argon2 cost matters, not the boolean outcome.
    assert verify_calls[0][1] == "ghost@example.com"


def test_password_reset_known_email_calls_verify_exactly_once(
    request_password_reset: RequestPasswordReset,
    register_use_case: RegisterUser,
    password_service: PasswordService,
) -> None:
    """Known-email branch: pays exactly one Argon2-class verify too.

    The known branch runs the audit + token-row writes inside
    ``issue_internal_token_transaction`` (~7 ms), which is much cheaper
    than an Argon2 verify (~30-40 ms). To match the unknown branch's
    wall-clock the known branch ALSO calls
    ``verify_password(FIXED_DUMMY_ARGON2_HASH, ...)`` once. The boolean
    is discarded; only the cost matters.
    """
    register_use_case.execute(email="known@example.com", password=PASSWORD)
    verify_calls = _spy_verify(password_service)

    result = request_password_reset.execute(email="known@example.com")

    assert isinstance(result, Ok)
    assert result.value.token is not None
    assert len(verify_calls) == 1, (
        f"Expected exactly one verify_password call on the known-email "
        f"branch (timing parity with the unknown-email branch), got "
        f"{len(verify_calls)}: {verify_calls!r}"
    )
    assert verify_calls[0][0] == FIXED_DUMMY_ARGON2_HASH


# ── RequestEmailVerification ─────────────────────────────────────────────────


def test_email_verification_unknown_user_calls_verify_exactly_once(
    request_email_verification: RequestEmailVerification,
    password_service: PasswordService,
) -> None:
    """Unknown-user branch: pays the Argon2 cost via one dummy-hash verify."""
    verify_calls = _spy_verify(password_service)

    unknown_user_id = uuid4()
    result = request_email_verification.execute(user_id=unknown_user_id)

    assert isinstance(result, Err)
    assert isinstance(result.error, NotFoundError)
    assert len(verify_calls) == 1, (
        f"Expected exactly one verify_password call on the unknown-user "
        f"branch (timing parity with the known-user branch), got "
        f"{len(verify_calls)}: {verify_calls!r}"
    )
    assert verify_calls[0][0] == FIXED_DUMMY_ARGON2_HASH
    assert verify_calls[0][1] == str(unknown_user_id)


def test_email_verification_known_user_calls_verify_exactly_once(
    request_email_verification: RequestEmailVerification,
    register_use_case: RegisterUser,
    users: FakeUserPort,
    password_service: PasswordService,
) -> None:
    """Known-user branch: pays exactly one Argon2-class verify too.

    Same shape as ``test_password_reset_known_email_calls_verify_exactly_once``
    — the dominant Argon2 cost is paid on both branches so wall-clock
    distributions overlap and the unknown branch is not enumerable.
    """
    reg = register_use_case.execute(email="known@example.com", password=PASSWORD)
    assert isinstance(reg, Ok)
    user_id = reg.value.id
    # Sanity: the user is reachable through the port.
    assert users.get_by_id(user_id) is not None

    verify_calls = _spy_verify(password_service)

    result = request_email_verification.execute(user_id=user_id)

    assert isinstance(result, Ok)
    assert result.value.token is not None
    assert len(verify_calls) == 1, (
        f"Expected exactly one verify_password call on the known-user "
        f"branch (timing parity with the unknown-user branch), got "
        f"{len(verify_calls)}: {verify_calls!r}"
    )
    assert verify_calls[0][0] == FIXED_DUMMY_ARGON2_HASH
    assert verify_calls[0][1] == str(user_id)
