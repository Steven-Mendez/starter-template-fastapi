"""Integration coverage for atomic refresh-token rotation."""

from __future__ import annotations

import threading
from uuid import UUID

import pytest

from src.features.authentication.adapters.outbound.persistence.sqlmodel.repository import (  # noqa: E501
    SQLModelAuthRepository,
)
from src.features.authentication.application.crypto import hash_token
from src.features.authentication.application.errors import InvalidTokenError
from src.features.authentication.application.types import IssuedTokens
from src.features.authentication.composition.container import build_auth_container
from src.platform.config.settings import AppSettings
from src.platform.shared.principal import Principal
from src.platform.shared.result import Ok

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
    container.register_user.execute(
        email="user@example.com", password="UserPassword123!"
    )
    login_result = container.login_user.execute(
        email="user@example.com", password="UserPassword123!"
    )
    assert isinstance(login_result, Ok)
    issued, _ = login_result.value

    token_service = container.rotate_refresh_token._token_service  # noqa: SLF001
    original_issue = token_service.issue
    first_issue_started = threading.Event()
    release_first_issue = threading.Event()
    second_reached_issue = threading.Event()
    issue_calls: list[str] = []
    issue_calls_lock = threading.Lock()

    def gated_issue(*, subject: UUID, authz_version: int) -> tuple[str, int]:
        with issue_calls_lock:
            issue_calls.append(threading.current_thread().name)
            call_number = len(issue_calls)
        if call_number == 1:
            first_issue_started.set()
            assert release_first_issue.wait(timeout=5)
        else:
            second_reached_issue.set()
        return original_issue(subject=subject, authz_version=authz_version)

    monkeypatch.setattr(token_service, "issue", gated_issue)

    successes: list[tuple[IssuedTokens, Principal]] = []
    errors: list[Exception] = []

    def run_refresh() -> None:
        try:
            result = container.rotate_refresh_token.execute(
                refresh_token=issued.refresh_token
            )
            match result:
                case Ok(value=pair):
                    successes.append(pair)
                case _ as err:
                    errors.append(err.error)
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
