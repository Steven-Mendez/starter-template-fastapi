"""Unit coverage for the ``DeactivateUser`` use case."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app_platform.shared.result import Err, Ok
from features.users.application.errors import UserNotFoundError
from features.users.application.use_cases.deactivate_user import DeactivateUser
from features.users.tests.fakes.fake_user_port import FakeUserPort

pytestmark = pytest.mark.unit


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
