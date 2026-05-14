"""Integration coverage for token-issuance wall-clock parity.

``RequestPasswordReset`` and ``RequestEmailVerification`` must not
leak account existence through response latency. Both branches call
``verify_password(FIXED_DUMMY_ARGON2_HASH, ...)`` exactly once so the
dominant Argon2 wall-clock cost is paid on both paths. The known
branch *additionally* runs the transactional audit + token-write
pipeline (~7 ms), which is small relative to the Argon2 cost. Mean
wall-clock delta should stay below 10 ms per tasks.md 4.4.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Ok
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authentication.composition.container import build_auth_container
from features.outbox.tests.fakes.fake_outbox import InlineDispatchOutboxUnitOfWork
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SessionSQLModelUserRepository,
    SQLModelUserRepository,
)

pytestmark = pytest.mark.integration

_MAX_MEAN_DELTA_SECONDS = 0.010
_ITERATIONS = 50


def _build_container(
    settings: AppSettings, repository: SQLModelAuthRepository
) -> object:
    users = SQLModelUserRepository(engine=repository.engine)
    return build_auth_container(
        settings=settings,
        users=users,
        outbox_uow=InlineDispatchOutboxUnitOfWork(dispatcher=lambda _n, _p: None),
        user_writer_factory=lambda session: SessionSQLModelUserRepository(
            session=session
        ),
        repository=repository,
    )


def test_password_reset_known_vs_unknown_mean_delta_below_threshold(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    """50 known + 50 unknown reset requests; mean delta < 10 ms."""
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_redis_url": None,
            "auth_rate_limit_enabled": False,
        }
    )
    container = _build_container(settings, postgres_auth_repository)
    known_email = "reset-known@example.com"
    reg = container.register_user.execute(  # type: ignore[attr-defined]
        email=known_email, password="UserPassword123!"
    )
    assert isinstance(reg, Ok)

    # Warm-up.
    for _ in range(3):
        container.request_password_reset.execute(email=known_email)  # type: ignore[attr-defined]
        container.request_password_reset.execute(email="warmup@example.com")  # type: ignore[attr-defined]

    known_durations: list[float] = []
    unknown_durations: list[float] = []
    for i in range(_ITERATIONS):
        t0 = time.perf_counter()
        known_result = container.request_password_reset.execute(  # type: ignore[attr-defined]
            email=known_email
        )
        known_durations.append(time.perf_counter() - t0)
        assert isinstance(known_result, Ok)

        t0 = time.perf_counter()
        unknown_result = container.request_password_reset.execute(  # type: ignore[attr-defined]
            email=f"ghost-{i}@example.com"
        )
        unknown_durations.append(time.perf_counter() - t0)
        assert isinstance(unknown_result, Ok)

    mean_known = sum(known_durations) / len(known_durations)
    mean_unknown = sum(unknown_durations) / len(unknown_durations)
    delta = abs(mean_known - mean_unknown)
    assert delta < _MAX_MEAN_DELTA_SECONDS, (
        f"Password-reset issuance mean wall-clock delta was "
        f"{delta * 1000:.2f} ms (known={mean_known * 1000:.2f} ms, "
        f"unknown={mean_unknown * 1000:.2f} ms); expected < "
        f"{_MAX_MEAN_DELTA_SECONDS * 1000:.0f} ms."
    )

    container.shutdown()  # type: ignore[attr-defined]


def test_email_verification_known_vs_unknown_mean_delta_below_threshold(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    """50 known + 50 unknown verify-issuance requests; mean delta < 10 ms."""
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_redis_url": None,
            "auth_rate_limit_enabled": False,
        }
    )
    container = _build_container(settings, postgres_auth_repository)
    reg = container.register_user.execute(  # type: ignore[attr-defined]
        email="verify-known@example.com", password="UserPassword123!"
    )
    assert isinstance(reg, Ok)
    known_user_id = reg.value.id

    # Warm-up.
    for _ in range(3):
        container.request_email_verification.execute(user_id=known_user_id)  # type: ignore[attr-defined]
        container.request_email_verification.execute(user_id=uuid4())  # type: ignore[attr-defined]

    known_durations: list[float] = []
    unknown_durations: list[float] = []
    for _ in range(_ITERATIONS):
        t0 = time.perf_counter()
        container.request_email_verification.execute(user_id=known_user_id)  # type: ignore[attr-defined]
        known_durations.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        container.request_email_verification.execute(user_id=uuid4())  # type: ignore[attr-defined]
        unknown_durations.append(time.perf_counter() - t0)

    mean_known = sum(known_durations) / len(known_durations)
    mean_unknown = sum(unknown_durations) / len(unknown_durations)
    delta = abs(mean_known - mean_unknown)
    assert delta < _MAX_MEAN_DELTA_SECONDS, (
        f"Email-verify issuance mean wall-clock delta was "
        f"{delta * 1000:.2f} ms (known={mean_known * 1000:.2f} ms, "
        f"unknown={mean_unknown * 1000:.2f} ms); expected < "
        f"{_MAX_MEAN_DELTA_SECONDS * 1000:.0f} ms."
    )

    container.shutdown()  # type: ignore[attr-defined]
