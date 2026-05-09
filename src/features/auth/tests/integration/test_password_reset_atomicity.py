"""Integration coverage for atomic password-reset token consumption."""

from __future__ import annotations

import threading

import pytest

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.auth.application.errors import TokenAlreadyUsedError
from src.features.auth.composition.container import build_auth_container
from src.platform.config.settings import AppSettings

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
    container = build_auth_container(
        settings=settings,
        repository=postgres_auth_repository,
    )
    auth = container.auth_service
    auth.register(email="reset-race@example.com", password="UserPassword123!")
    reset = auth.request_password_reset(email="reset-race@example.com")
    assert reset.token is not None

    original_hash = auth._passwords.hash_password  # noqa: SLF001
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

    monkeypatch.setattr(auth._passwords, "hash_password", gated_hash)  # noqa: SLF001

    successes: list[None] = []
    errors: list[Exception] = []

    def run_reset() -> None:
        try:
            auth.reset_password(
                token=reset.token or "",
                new_password="NewUserPassword123!",
            )
            successes.append(None)
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
