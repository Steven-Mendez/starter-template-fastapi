"""Integration coverage for login wall-clock parity (hit vs miss).

The defence we ship is "exactly one Argon2 verify on both branches plus
identical DB roundtrip counts". The wall-clock observable should
therefore overlap between hit and miss to within the noise floor.
``< 5 ms`` mean delta is the bar set by tasks.md 1.5.

Argon2 dominates (~150 ms by default); network/IO jitter dwarfs the few
extra ms a real DB roundtrip would add. If this test ever fails it
indicates either a re-introduced extra DB call on one branch or a
removed dummy-hash verify on the other.
"""

from __future__ import annotations

import time

import pytest

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok
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

# Argon2 default parameters give ~150 ms per verify; a 5 ms mean delta
# is well inside the parity envelope and far above measurement noise
# for the ~150 ms unit cost.
_MAX_MEAN_DELTA_SECONDS = 0.005
# 100 hits and 100 misses per tasks.md 1.5. Keeping iteration counts
# parameterised so the test is easy to retune if Argon2 parameters
# change.
_ITERATIONS = 100


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


def test_login_hit_vs_miss_mean_wall_clock_delta_is_below_threshold(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    """100 hits and 100 misses; mean wall-clock delta < 5 ms.

    The known-email branch verifies the stored credential hash; the
    unknown-email branch verifies the fixed dummy hash. Both call
    ``verify_password`` exactly once and issue exactly one
    ``get_credential_for_user`` roundtrip — so the wall-clock should
    overlap once Argon2 dominates.
    """
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_redis_url": None,
            "auth_rate_limit_enabled": False,
        }
    )
    container = _build_container(settings, postgres_auth_repository)
    known_email = "known@example.com"
    known_password = "UserPassword123!"
    wrong_password = "WrongPassword999!"
    reg = container.register_user.execute(  # type: ignore[attr-defined]
        email=known_email, password=known_password
    )
    assert isinstance(reg, Ok)

    # Warm-up: prime the argon2 hasher / pool / JIT-style caches so the
    # first iteration doesn't skew the mean.
    for _ in range(3):
        container.login_user.execute(  # type: ignore[attr-defined]
            email=known_email, password=wrong_password
        )
        container.login_user.execute(  # type: ignore[attr-defined]
            email="warmup@example.com", password=wrong_password
        )

    hit_durations: list[float] = []
    miss_durations: list[float] = []
    # Interleave hits and misses so transient system noise (GC, page
    # cache evictions, neighbour-tenant CPU stalls) hits both samples
    # equally — averaging over a contiguous block of misses would let
    # noise on one block bias the delta.
    for i in range(_ITERATIONS):
        t0 = time.perf_counter()
        hit_result = container.login_user.execute(  # type: ignore[attr-defined]
            email=known_email, password=wrong_password
        )
        hit_durations.append(time.perf_counter() - t0)
        assert isinstance(hit_result, Err)

        t0 = time.perf_counter()
        miss_result = container.login_user.execute(  # type: ignore[attr-defined]
            email=f"ghost-{i}@example.com", password=wrong_password
        )
        miss_durations.append(time.perf_counter() - t0)
        assert isinstance(miss_result, Err)

    mean_hit = sum(hit_durations) / len(hit_durations)
    mean_miss = sum(miss_durations) / len(miss_durations)
    delta = abs(mean_hit - mean_miss)
    assert delta < _MAX_MEAN_DELTA_SECONDS, (
        f"Mean wall-clock delta between login hit and miss branches was "
        f"{delta * 1000:.2f} ms (hit={mean_hit * 1000:.2f} ms, "
        f"miss={mean_miss * 1000:.2f} ms); expected < "
        f"{_MAX_MEAN_DELTA_SECONDS * 1000:.0f} ms. A timing channel may "
        f"have been re-introduced."
    )

    container.shutdown()  # type: ignore[attr-defined]
