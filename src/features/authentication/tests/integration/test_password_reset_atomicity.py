"""Integration coverage for atomic password-reset token consumption."""

from __future__ import annotations

import threading

import pytest

from src.features.authentication.adapters.outbound.persistence.sqlmodel.repository import (  # noqa: E501
    SQLModelAuthRepository,
)
from src.features.authentication.application.errors import TokenAlreadyUsedError
from src.features.authentication.composition.container import build_auth_container
from src.features.background_jobs.tests.fakes.fake_job_queue import FakeJobQueue
from src.features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from src.platform.config.settings import AppSettings
from src.platform.shared.result import Ok

pytestmark = pytest.mark.integration


def test_concurrent_password_reset_serializes_on_token_row(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_redis_url": None,
        }
    )
    users = SQLModelUserRepository(engine=postgres_auth_repository.engine)
    container = build_auth_container(
        settings=settings,
        users=users,
        jobs=FakeJobQueue(),
        repository=postgres_auth_repository,
    )
    reg = container.register_user.execute(
        email="reset-race@example.com", password="UserPassword123!"
    )
    assert isinstance(reg, Ok)

    reset_result = container.request_password_reset.execute(
        email="reset-race@example.com"
    )
    assert isinstance(reset_result, Ok)
    reset = reset_result.value
    assert reset.token is not None

    password_service = container.confirm_password_reset._password_service  # noqa: SLF001
    original_hash = password_service.hash_password
    first_hash_started = threading.Event()
    release_first_hash = threading.Event()
    hash_calls: list[str] = []
    hash_calls_lock = threading.Lock()

    def gated_hash(password: str) -> str:
        with hash_calls_lock:
            hash_calls.append(threading.current_thread().name)
            call_number = len(hash_calls)
        if call_number == 1:
            first_hash_started.set()
            assert release_first_hash.wait(timeout=5)
        return original_hash(password)

    monkeypatch.setattr(password_service, "hash_password", gated_hash)

    successes: list[None] = []
    errors: list[Exception] = []

    def run_reset() -> None:
        try:
            result = container.confirm_password_reset.execute(
                token=reset.token or "",
                new_password="NewUserPassword123!",
            )
            match result:
                case Ok():
                    successes.append(None)
                case _ as err:
                    errors.append(err.error)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    first = threading.Thread(target=run_reset, name="reset-1")
    second = threading.Thread(target=run_reset, name="reset-2")

    first.start()
    assert first_hash_started.wait(timeout=5)
    second.start()
    assert len(successes) == 0
    assert len(errors) == 0

    release_first_hash.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], TokenAlreadyUsedError)

    container.shutdown()
