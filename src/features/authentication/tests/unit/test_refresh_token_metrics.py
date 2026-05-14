"""Section 4.1: ``RotateRefreshToken`` increments ``app_auth_refresh_total``.

The use case is wrapped in a single-exit increment shim: regardless of
which Err branch is taken inside ``_execute``, the outer ``execute``
records exactly one data point. These tests drive each branch and
assert exactly one increment with the correct ``result`` label.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
from app_platform.tests.unit.observability._metric_helpers import (
    CounterHarness,
    install_counter,
)
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
EMAIL = "refresh-metrics@example.com"


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


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> CounterHarness:
    return install_counter(
        monkeypatch,
        name="app_auth_refresh_total",
        attr_name="AUTH_REFRESH_TOTAL",
        modules=[
            "app_platform.observability.metrics",
            "features.authentication.application.use_cases.auth.refresh_token",
        ],
    )


def test_rotate_success_increments_success_exactly_once(
    rotate: RotateRefreshToken,
    issued_refresh_token: str,
    counter: CounterHarness,
) -> None:
    result = rotate.execute(refresh_token=issued_refresh_token)

    assert isinstance(result, Ok)
    assert counter.total(result="success") == 1
    assert counter.total(result="failure") == 0


def test_rotate_missing_token_increments_failure_exactly_once(
    rotate: RotateRefreshToken,
    counter: CounterHarness,
) -> None:
    """An empty / ``None`` refresh token is the fast-path Err branch."""
    result = rotate.execute(refresh_token=None)

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidTokenError)
    assert counter.total(result="failure") == 1
    assert counter.total(result="success") == 0


def test_rotate_unknown_token_increments_failure_exactly_once(
    rotate: RotateRefreshToken,
    counter: CounterHarness,
) -> None:
    """A token that doesn't match any stored hash records exactly one failure."""
    result = rotate.execute(refresh_token="never-issued-token")

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidTokenError)
    assert counter.total(result="failure") == 1
    assert counter.total(result="success") == 0


def test_rotate_expired_token_increments_failure_exactly_once(
    rotate: RotateRefreshToken,
    users: FakeUserPort,
    repository: FakeAuthRepository,
    counter: CounterHarness,
) -> None:
    user_result = users.create(email="rot-expired@example.com")
    assert isinstance(user_result, Ok)
    raw = "expired-refresh-token-metric"
    repository.create_refresh_token(
        user_id=user_result.value.id,
        token_hash=hash_token(raw),
        family_id=uuid4(),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        created_ip=None,
        user_agent=None,
    )

    result = rotate.execute(refresh_token=raw)

    assert isinstance(result, Err)
    assert isinstance(result.error, InvalidTokenError)
    assert counter.total(result="failure") == 1
    assert counter.total(result="success") == 0


def test_rotate_reuse_of_revoked_token_increments_failure_exactly_once(
    rotate: RotateRefreshToken,
    issued_refresh_token: str,
    counter: CounterHarness,
) -> None:
    """Family-revocation path is still a single failure increment."""
    first = rotate.execute(refresh_token=issued_refresh_token)
    assert isinstance(first, Ok)

    # Reusing the original (now-rotated) token revokes the whole family;
    # the outer wrapper still records EXACTLY one increment for the
    # second call.
    second = rotate.execute(refresh_token=issued_refresh_token)
    assert isinstance(second, Err)
    # First call succeeded; the reuse failed. So we expect 1 success + 1 failure.
    assert counter.total(result="success") == 1
    assert counter.total(result="failure") == 1


def test_rotate_records_only_result_attribute(
    rotate: RotateRefreshToken,
    issued_refresh_token: str,
    counter: CounterHarness,
) -> None:
    """4.4 regression: the call site supplies only the ``result`` attribute."""
    rotate.execute(refresh_token=issued_refresh_token)

    for attrs, _ in counter.points():
        assert set(attrs.keys()) == {"result"}, (
            f"refresh counter emitted unexpected label keys: {set(attrs.keys())}"
        )
