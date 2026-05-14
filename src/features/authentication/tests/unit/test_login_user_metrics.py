"""Section 4.1: ``LoginUser`` increments ``app_auth_logins_total`` once per call.

Every Ok branch must increment ``result="success"`` exactly once; every
Err branch must increment ``result="failure"`` exactly once. The login
use case has three documented failure branches (invalid creds, inactive
user, email-not-verified) plus one success branch — all four are
exercised here.
"""

from __future__ import annotations

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from app_platform.tests.unit.observability._metric_helpers import (
    CounterHarness,
    install_counter,
)
from features.authentication.application.crypto import PasswordService
from features.authentication.application.errors import (
    EmailNotVerifiedError,
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
        auth_require_email_verification=False,
    )


@pytest.fixture
def settings_require_verification() -> AppSettings:
    return AppSettings(
        environment="test",
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
        auth_require_email_verification=True,
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


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> CounterHarness:
    """Swap ``AUTH_LOGINS_TOTAL`` with a fresh in-memory counter.

    The use case grabbed the module-level counter at import time, so
    we must patch BOTH the metrics module and the use-case module.
    """
    return install_counter(
        monkeypatch,
        name="app_auth_logins_total",
        attr_name="AUTH_LOGINS_TOTAL",
        modules=[
            "app_platform.observability.metrics",
            "features.authentication.application.use_cases.auth.login_user",
        ],
    )


def test_login_success_increments_success_exactly_once(
    login_use_case: LoginUser,
    register_use_case: RegisterUser,
    counter: CounterHarness,
) -> None:
    register_use_case.execute(email="ok@example.com", password=PASSWORD)

    result = login_use_case.execute(email="ok@example.com", password=PASSWORD)

    assert isinstance(result, Ok)
    assert counter.total(result="success") == 1
    assert counter.total(result="failure") == 0


def test_login_invalid_credentials_increments_failure_exactly_once(
    login_use_case: LoginUser,
    register_use_case: RegisterUser,
    counter: CounterHarness,
) -> None:
    register_use_case.execute(email="wrong@example.com", password=PASSWORD)

    result = login_use_case.execute(email="wrong@example.com", password="Nope1234!")

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidCredentialsError)
    assert counter.total(result="failure") == 1
    assert counter.total(result="success") == 0


def test_login_unknown_email_increments_failure_exactly_once(
    login_use_case: LoginUser,
    counter: CounterHarness,
) -> None:
    result = login_use_case.execute(email="ghost@example.com", password="Whatever1!")

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidCredentialsError)
    assert counter.total(result="failure") == 1
    assert counter.total(result="success") == 0


def test_login_inactive_user_increments_failure_exactly_once(
    login_use_case: LoginUser,
    register_use_case: RegisterUser,
    users: FakeUserPort,
    counter: CounterHarness,
) -> None:
    reg = register_use_case.execute(email="inactive@example.com", password=PASSWORD)
    assert isinstance(reg, Ok)
    users.set_active(reg.value.id, is_active=False)

    result = login_use_case.execute(email="inactive@example.com", password=PASSWORD)

    assert isinstance(result, Err)
    assert isinstance(result.error, InactiveUserError)
    assert counter.total(result="failure") == 1
    assert counter.total(result="success") == 0


def test_login_unverified_email_increments_failure_exactly_once(
    users: FakeUserPort,
    repository: FakeAuthRepository,
    password_service: PasswordService,
    register_use_case: RegisterUser,
    settings_require_verification: AppSettings,
    counter: CounterHarness,
) -> None:
    # Build a use case with the verification-required setting and
    # leave the just-registered user unverified.
    use_case = LoginUser(
        _users=users,
        _repository=repository,
        _password_service=password_service,
        _token_service=AccessTokenService(settings_require_verification),
        _settings=settings_require_verification,
    )
    reg = register_use_case.execute(email="unverified@example.com", password=PASSWORD)
    assert isinstance(reg, Ok)

    result = use_case.execute(email="unverified@example.com", password=PASSWORD)

    assert isinstance(result, Err)
    assert isinstance(result.error, EmailNotVerifiedError)
    assert counter.total(result="failure") == 1
    assert counter.total(result="success") == 0


def test_login_success_uses_only_result_attribute(
    login_use_case: LoginUser,
    register_use_case: RegisterUser,
    counter: CounterHarness,
) -> None:
    """4.4 regression at the call site: only ``result`` is set, no extras."""
    register_use_case.execute(email="card@example.com", password=PASSWORD)
    login_use_case.execute(email="card@example.com", password=PASSWORD)

    for attrs, _ in counter.points():
        assert set(attrs.keys()) == {"result"}, (
            f"login counter emitted unexpected label keys: {set(attrs.keys())}"
        )


def test_login_repeated_calls_aggregate_increments(
    login_use_case: LoginUser,
    register_use_case: RegisterUser,
    counter: CounterHarness,
) -> None:
    """Three successes + two failures = exactly five data points summed."""
    register_use_case.execute(email="repeat@example.com", password=PASSWORD)
    for _ in range(3):
        assert isinstance(
            login_use_case.execute(email="repeat@example.com", password=PASSWORD), Ok
        )
    for _ in range(2):
        assert isinstance(
            login_use_case.execute(email="repeat@example.com", password="WrongPw1!"),
            Err,
        )
    assert counter.total(result="success") == 3
    assert counter.total(result="failure") == 2
