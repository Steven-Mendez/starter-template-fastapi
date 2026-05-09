"""Integration coverage for atomic refresh-token rotation."""

from __future__ import annotations

import threading
from uuid import UUID

import pytest

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.auth.application.crypto import hash_token
from src.features.auth.application.errors import InvalidTokenError
from src.features.auth.application.types import IssuedTokens, Principal
from src.features.auth.composition.container import build_auth_container
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.integration


def test_concurrent_refresh_serializes_on_presented_token_row(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_redis_url": None,
        }
    )
    container = build_auth_container(
        settings=settings,
        repository=postgres_auth_repository,
    )
    auth = container.auth_service
    auth.register(email="user@example.com", password="UserPassword123!")
    issued, _ = auth.login(email="user@example.com", password="UserPassword123!")

    original_issue = auth._tokens.issue  # noqa: SLF001
    first_issue_started = threading.Event()
    release_first_issue = threading.Event()
    second_reached_issue = threading.Event()
    issue_calls: list[str] = []
    issue_calls_lock = threading.Lock()

    def gated_issue(
        *, subject: UUID, roles: set[str], authz_version: int
    ) -> tuple[str, int]:
        with issue_calls_lock:
            issue_calls.append(threading.current_thread().name)
            call_number = len(issue_calls)
        if call_number == 1:
            first_issue_started.set()
            assert release_first_issue.wait(timeout=5)
        else:
            second_reached_issue.set()
        return original_issue(subject=subject, roles=roles, authz_version=authz_version)

    monkeypatch.setattr(auth._tokens, "issue", gated_issue)  # noqa: SLF001

    successes: list[tuple[IssuedTokens, Principal]] = []
    errors: list[Exception] = []

    def run_refresh() -> None:
        try:
            successes.append(auth.refresh(refresh_token=issued.refresh_token))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    first = threading.Thread(target=run_refresh, name="refresh-1")
    second = threading.Thread(target=run_refresh, name="refresh-2")

    first.start()
    assert first_issue_started.wait(timeout=5)
    second.start()
    assert not second_reached_issue.wait(timeout=0.25)

    release_first_issue.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(issue_calls) == 1
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], InvalidTokenError)

    rotated_refresh = successes[0][0].refresh_token
    rotated_record = postgres_auth_repository.get_refresh_token_by_hash(
        hash_token(rotated_refresh)
    )
    assert rotated_record is not None
    assert rotated_record.revoked_at is not None
