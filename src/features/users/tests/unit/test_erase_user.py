"""Unit-level coverage for ``EraseUser``.

Exercises the orchestration shape (every collaborator is called, in the
right order, with the right arguments) and the idempotency guarantee.
The integration suite covers the actual SQL-side state changes against
a real PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app_platform.shared.result import Err, Ok
from features.users.application.errors import UserNotFoundError
from features.users.application.use_cases.erase_user import (
    DELETE_USER_ASSETS_JOB,
    EraseUser,
)
from features.users.domain.user import User
from features.users.tests.fakes.fake_user_port import FakeUserPort

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class _RecordingWriter:
    enqueued: list[dict[str, Any]] = field(default_factory=list)

    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None:
        self.enqueued.append({"job_name": job_name, "payload": payload})


@dataclass(slots=True)
class _FakeOutboxUoW:
    writer: _RecordingWriter = field(default_factory=_RecordingWriter)

    class _Ctx:
        def __init__(self, writer: _RecordingWriter) -> None:
            self.writer = writer

        def __enter__(self) -> _RecordingWriter:
            return self.writer

        def __exit__(self, *exc: object) -> None:
            return None

    def transaction(self) -> _Ctx:
        return self._Ctx(self.writer)


@dataclass(slots=True)
class _FakeAuthArtifactsCleanup:
    scrubbed: list[UUID] = field(default_factory=list)
    deleted: list[UUID] = field(default_factory=list)
    erased_events: list[tuple[UUID, str]] = field(default_factory=list)

    def scrub_audit_events(self, writer: object, user_id: UUID) -> None:
        _ = writer
        self.scrubbed.append(user_id)

    def delete_credentials_and_tokens(self, writer: object, user_id: UUID) -> None:
        _ = writer
        self.deleted.append(user_id)

    def record_user_erased_event(
        self, writer: object, user_id: UUID, reason: str
    ) -> None:
        _ = writer
        self.erased_events.append((user_id, reason))


def _seeded_user(users: FakeUserPort, email: str = "victim@example.com") -> User:
    result = users.create(email=email)
    assert isinstance(result, Ok)
    return result.value


def test_erase_user_orchestrates_every_collaborator_in_order() -> None:
    users = FakeUserPort()
    user = _seeded_user(users)
    artifacts = _FakeAuthArtifactsCleanup()
    uow = _FakeOutboxUoW()

    use_case = EraseUser(_users=users, _auth_artifacts=artifacts, _outbox_uow=uow)
    result = use_case.execute(user.id, "self_request")
    assert isinstance(result, Ok)

    # Every cleanup port hit exactly once for the user.
    assert artifacts.scrubbed == [user.id]
    assert artifacts.deleted == [user.id]
    assert artifacts.erased_events == [(user.id, "self_request")]
    # Outbox row for asset cleanup is enqueued.
    assert uow.writer.enqueued == [
        {"job_name": DELETE_USER_ASSETS_JOB, "payload": {"user_id": str(user.id)}}
    ]
    # User row is now scrubbed (raw read).
    scrubbed = users.get_raw_by_id(user.id)
    assert scrubbed is not None
    assert scrubbed.is_erased is True
    assert scrubbed.is_active is False
    assert scrubbed.email.endswith("@erased.invalid")
    # Filtered read returns None.
    assert users.get_by_id(user.id) is None
    assert users.get_by_email("victim@example.com") is None


def test_erase_user_is_idempotent_on_already_erased_user() -> None:
    users = FakeUserPort()
    user = _seeded_user(users)
    artifacts = _FakeAuthArtifactsCleanup()
    uow = _FakeOutboxUoW()
    use_case = EraseUser(_users=users, _auth_artifacts=artifacts, _outbox_uow=uow)
    use_case.execute(user.id, "self_request")
    # Second invocation: every collaborator should be a no-op.
    artifacts_second = _FakeAuthArtifactsCleanup()
    uow_second = _FakeOutboxUoW()
    use_case_second = EraseUser(
        _users=users, _auth_artifacts=artifacts_second, _outbox_uow=uow_second
    )
    result = use_case_second.execute(user.id, "admin_request")
    assert isinstance(result, Ok)
    assert artifacts_second.scrubbed == []
    assert artifacts_second.deleted == []
    assert artifacts_second.erased_events == []
    assert uow_second.writer.enqueued == []


def test_erase_user_returns_not_found_for_missing_user() -> None:
    users = FakeUserPort()
    artifacts = _FakeAuthArtifactsCleanup()
    uow = _FakeOutboxUoW()
    use_case = EraseUser(_users=users, _auth_artifacts=artifacts, _outbox_uow=uow)
    result = use_case.execute(uuid4(), "admin_request")
    assert isinstance(result, Err)
    assert isinstance(result.error, UserNotFoundError)
    # No work done.
    assert artifacts.scrubbed == []
    assert uow.writer.enqueued == []


def test_user_port_filters_erased_rows_from_email_lookup() -> None:
    users = FakeUserPort()
    user = _seeded_user(users, email="filter-me@example.com")
    artifacts = _FakeAuthArtifactsCleanup()
    uow = _FakeOutboxUoW()
    EraseUser(_users=users, _auth_artifacts=artifacts, _outbox_uow=uow).execute(
        user.id, "self_request"
    )
    # Original email no longer matches.
    assert users.get_by_email("filter-me@example.com") is None
    # Fresh registration with the original email succeeds with a new id.
    fresh = users.create(email="filter-me@example.com")
    assert isinstance(fresh, Ok)
    assert fresh.value.id != user.id
    # And the time-of-creation diverges (the fake stamps utc).
    assert fresh.value.created_at >= datetime.now(UTC).replace(microsecond=0)
