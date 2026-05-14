"""Unit coverage for the ``DeactivateUser`` use case."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app_platform.shared.result import Err, Ok
from features.outbox.application.ports.outbox_uow_port import OutboxWriter
from features.users.application.errors import UserNotFoundError
from features.users.application.use_cases.deactivate_user import (
    DELETE_USER_ASSETS_JOB,
    DeactivateUser,
)
from features.users.tests.fakes.fake_user_port import FakeUserPort

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class _RecordingWriter:
    """OutboxWriter capturing enqueued rows for assertions."""

    enqueued: list[tuple[str, dict[str, Any], datetime | None]] = field(
        default_factory=list
    )

    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None:
        self.enqueued.append((job_name, dict(payload), available_at))


@dataclass(slots=True)
class _RecordingOutboxUoW:
    """OutboxUnitOfWorkPort fake that tracks commit vs rollback."""

    writers: list[_RecordingWriter] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0

    @contextmanager
    def transaction(self) -> Iterator[OutboxWriter]:
        writer = _RecordingWriter()
        self.writers.append(writer)
        try:
            yield writer
            self.commits += 1
        except Exception:
            self.rollbacks += 1
            raise


def _make_user(users: FakeUserPort, email: str = "u@example.com") -> UUID:
    result = users.create(email=email)
    assert isinstance(result, Ok)
    return result.value.id


def test_deactivate_user_flips_is_active_and_bumps_authz_version() -> None:
    users = FakeUserPort()
    user_id = _make_user(users)
    use_case = DeactivateUser(_users=users)

    before = users.get_by_id(user_id)
    assert before is not None
    before_version = before.authz_version

    result = use_case.execute(user_id)

    assert isinstance(result, Ok)
    after = users.get_by_id(user_id)
    assert after is not None
    assert after.is_active is False
    assert after.authz_version == before_version + 1


def test_deactivate_user_returns_not_found_when_user_missing() -> None:
    users = FakeUserPort()
    use_case = DeactivateUser(_users=users)
    invocations: list[UUID] = []
    use_case._revoke_all_refresh_tokens = invocations.append

    result = use_case.execute(uuid4())

    assert isinstance(result, Err)
    assert isinstance(result.error, UserNotFoundError)
    # No revoke when the user was never found — the use case must not
    # propagate a missing-user condition to the revoker.
    assert invocations == []


def test_deactivate_user_invokes_revoker_with_same_user_id_in_same_uow() -> None:
    """The revoker must be called with the same id, before the is_active flip.

    "Same Unit of Work" is preserved by ordering: the revoker runs while
    the user row still reads ``is_active=True``. If the revoker were to
    fail (e.g. propagated an exception), the flip must not have happened
    yet — pinning the ordering here documents that contract.
    """
    users = FakeUserPort()
    user_id = _make_user(users)
    observed: list[tuple[UUID, bool]] = []

    def revoke(target: UUID) -> None:
        # Capture the user's is_active state at the moment the revoker
        # runs — it must still be True so a downstream rollback would
        # leave the user untouched.
        snapshot = users.get_by_id(target)
        assert snapshot is not None
        observed.append((target, snapshot.is_active))

    use_case = DeactivateUser(_users=users, _revoke_all_refresh_tokens=revoke)

    result = use_case.execute(user_id)

    assert isinstance(result, Ok)
    assert observed == [(user_id, True)]
    after = users.get_by_id(user_id)
    assert after is not None
    assert after.is_active is False


def test_deactivate_user_revoker_failure_aborts_deactivation() -> None:
    """A revoker exception must surface and leave the user active.

    The use case does not catch the revoker's exception: a failed revoke
    must abort the flip so the response never reports success when the
    server-side refresh families are still alive.
    """
    users = FakeUserPort()
    user_id = _make_user(users)

    def revoke(_: UUID) -> None:
        raise RuntimeError("boom")

    use_case = DeactivateUser(_users=users, _revoke_all_refresh_tokens=revoke)

    with pytest.raises(RuntimeError, match="boom"):
        use_case.execute(user_id)

    after = users.get_by_id(user_id)
    assert after is not None
    assert after.is_active is True


def test_deactivate_user_enqueues_delete_user_assets_outbox_row() -> None:
    """An ``outbox_uow``-wired use case writes one row inside the transaction.

    The row must use the canonical job name and a payload carrying the
    user id as a string (JSON-friendly). The commit must happen before
    the use case returns ``Ok``.
    """
    users = FakeUserPort()
    user_id = _make_user(users)
    outbox = _RecordingOutboxUoW()
    use_case = DeactivateUser(_users=users, _outbox_uow=outbox)

    result = use_case.execute(user_id)

    assert isinstance(result, Ok)
    assert outbox.commits == 1
    assert outbox.rollbacks == 0
    assert len(outbox.writers) == 1
    writer = outbox.writers[0]
    assert len(writer.enqueued) == 1
    job_name, payload, available_at = writer.enqueued[0]
    assert job_name == DELETE_USER_ASSETS_JOB
    assert payload == {"user_id": str(user_id)}
    assert available_at is None


def test_deactivate_user_does_not_enqueue_when_user_missing() -> None:
    """Missing users short-circuit before the outbox transaction opens."""
    users = FakeUserPort()
    outbox = _RecordingOutboxUoW()
    use_case = DeactivateUser(_users=users, _outbox_uow=outbox)

    result = use_case.execute(uuid4())

    assert isinstance(result, Err)
    assert isinstance(result.error, UserNotFoundError)
    assert outbox.commits == 0
    assert outbox.writers == []


def test_deactivate_user_without_outbox_uow_falls_back_to_direct_set_active() -> None:
    """Backwards-compat: no outbox wired ⇒ deactivation still completes."""
    users = FakeUserPort()
    user_id = _make_user(users)
    use_case = DeactivateUser(_users=users, _outbox_uow=None)

    result = use_case.execute(user_id)

    assert isinstance(result, Ok)
    after = users.get_by_id(user_id)
    assert after is not None
    assert after.is_active is False
