"""Unit tests for ``BootstrapSystemAdmin``.

Covers the four behavioral branches of the decision tree introduced in
``fix-bootstrap-admin-escalation`` plus the cache-invalidation contract
inherited from ``make-authz-grant-atomic``:

1. No existing user → create-and-grant, ``subevent="created"``.
2. Existing user already holds ``system:main#admin`` → idempotent no-op.
3. Existing non-admin user, ``promote_existing=False`` → refusal.
4. Existing non-admin user, ``promote_existing=True``, wrong password →
   refusal.
5. Existing non-admin user, ``promote_existing=True``, correct
   password → promotion, ``subevent="promoted_existing"``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app_platform.shared.result import Err, Ok, Result
from features.authorization.application.errors import (
    BootstrapPasswordMismatchError,
    BootstrapRefusedExistingUserError,
    CredentialVerificationError,
)
from features.authorization.application.types import Relationship
from features.authorization.application.use_cases import BootstrapSystemAdmin

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class _FakeUserRegistrar:
    """Returns a fixed user id and records the credentials it was called with."""

    user_id: UUID
    existing: UUID | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)
    lookups: list[str] = field(default_factory=list)

    def register_or_lookup(self, *, email: str, password: str) -> UUID:
        self.calls.append((email, password))
        return self.user_id

    def lookup_by_email(self, *, email: str) -> UUID | None:
        self.lookups.append(email)
        return self.existing


@dataclass(slots=True)
class _FakeAuthorization:
    """Records every ``write_relationships`` call.

    ``check_result`` controls the return of :meth:`check`; the default
    is ``False`` so the use case treats an existing user as
    non-admin unless a test overrides it.
    """

    writes: list[list[Relationship]] = field(default_factory=list)
    check_result: bool = False
    check_calls: list[tuple[UUID, str, str, str]] = field(default_factory=list)

    def write_relationships(self, tuples: list[Relationship]) -> None:
        self.writes.append(list(tuples))

    def check(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        self.check_calls.append((user_id, action, resource_type, resource_id))
        return self.check_result


@dataclass(slots=True)
class _FakeAudit:
    """Captures audit events for assertions."""

    events: list[tuple[str, UUID | None, dict[str, object] | None]] = field(
        default_factory=list
    )

    def record(
        self,
        event_type: str,
        *,
        user_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.events.append((event_type, user_id, metadata))


@dataclass(slots=True)
class _RecordingInvalidator:
    """Records each ``invalidate_user`` call."""

    invalidated: list[UUID] = field(default_factory=list)

    def invalidate_user(self, user_id: UUID) -> None:
        self.invalidated.append(user_id)


@dataclass(slots=True)
class _RaisingInvalidator:
    """Always raises to simulate a Redis blip."""

    error: Exception

    def invalidate_user(self, user_id: UUID) -> None:
        del user_id
        raise self.error


@dataclass(slots=True)
class _AcceptVerifier:
    """Verifier that always returns ``Ok`` (used to assert promote success)."""

    calls: list[tuple[UUID, str]] = field(default_factory=list)

    def verify(
        self, user_id: UUID, password: str
    ) -> Result[None, CredentialVerificationError]:
        self.calls.append((user_id, password))
        return Ok(None)


@dataclass(slots=True)
class _RejectVerifier:
    """Verifier that always returns ``Err`` (used to assert wrong-password refusal)."""

    calls: list[tuple[UUID, str]] = field(default_factory=list)

    def verify(
        self, user_id: UUID, password: str
    ) -> Result[None, CredentialVerificationError]:
        self.calls.append((user_id, password))
        return Err(CredentialVerificationError(user_id))


@dataclass(slots=True)
class _NeverCalledVerifier:
    """Verifier that fails the test if invoked (path b/c/d should not call it)."""

    def verify(
        self, user_id: UUID, password: str
    ) -> Result[None, CredentialVerificationError]:
        del user_id, password
        raise AssertionError("CredentialVerifierPort.verify must not be called")


def test_bootstrap_creates_user_when_none_exists() -> None:
    user_id = uuid4()
    registrar = _FakeUserRegistrar(user_id=user_id, existing=None)
    auth = _FakeAuthorization()
    audit = _FakeAudit()
    invalidator = _RecordingInvalidator()
    use_case = BootstrapSystemAdmin(
        _authorization=auth,  # type: ignore[arg-type]
        _user_registrar=registrar,
        _credential_verifier=_NeverCalledVerifier(),
        _audit=audit,
        _principal_cache_invalidator=invalidator,
        _promote_existing=False,
    )

    result = use_case.execute(email="admin@example.com", password="pw")

    assert isinstance(result, Ok)
    assert result.value == user_id
    assert registrar.calls == [("admin@example.com", "pw")]
    assert len(auth.writes) == 1
    assert auth.writes[0][0].subject_id == str(user_id)
    assert invalidator.invalidated == [user_id]
    assert len(audit.events) == 1
    event_type, audit_user_id, metadata = audit.events[0]
    assert event_type == "authz.system_admin_bootstrapped"
    assert audit_user_id == user_id
    assert metadata is not None
    assert metadata["subevent"] == "created"
    assert metadata["actor"] == "system"
    assert metadata["reason"] == "bootstrap_on_startup"


def test_bootstrap_is_idempotent_when_user_already_holds_admin() -> None:
    existing = uuid4()
    registrar = _FakeUserRegistrar(user_id=uuid4(), existing=existing)
    auth = _FakeAuthorization(check_result=True)
    audit = _FakeAudit()
    invalidator = _RecordingInvalidator()
    use_case = BootstrapSystemAdmin(
        _authorization=auth,  # type: ignore[arg-type]
        _user_registrar=registrar,
        _credential_verifier=_NeverCalledVerifier(),
        _audit=audit,
        _principal_cache_invalidator=invalidator,
        _promote_existing=False,
    )

    result = use_case.execute(email="admin@example.com", password="pw")

    assert isinstance(result, Ok)
    assert result.value == existing
    assert registrar.calls == []
    assert auth.writes == []
    assert audit.events == []
    assert invalidator.invalidated == []


def test_bootstrap_refuses_existing_non_admin_without_optin() -> None:
    existing = uuid4()
    registrar = _FakeUserRegistrar(user_id=uuid4(), existing=existing)
    auth = _FakeAuthorization(check_result=False)
    audit = _FakeAudit()
    invalidator = _RecordingInvalidator()
    use_case = BootstrapSystemAdmin(
        _authorization=auth,  # type: ignore[arg-type]
        _user_registrar=registrar,
        _credential_verifier=_NeverCalledVerifier(),
        _audit=audit,
        _principal_cache_invalidator=invalidator,
        _promote_existing=False,
    )

    result = use_case.execute(email="admin@example.com", password="pw")

    assert isinstance(result, Err)
    err = result.error
    assert isinstance(err, BootstrapRefusedExistingUserError)
    assert err.user_id == existing
    assert err.email == "admin@example.com"
    assert auth.writes == []
    assert audit.events == []
    assert invalidator.invalidated == []


def test_bootstrap_promotes_existing_user_with_correct_password() -> None:
    existing = uuid4()
    registrar = _FakeUserRegistrar(user_id=uuid4(), existing=existing)
    auth = _FakeAuthorization(check_result=False)
    audit = _FakeAudit()
    invalidator = _RecordingInvalidator()
    verifier = _AcceptVerifier()
    use_case = BootstrapSystemAdmin(
        _authorization=auth,  # type: ignore[arg-type]
        _user_registrar=registrar,
        _credential_verifier=verifier,
        _audit=audit,
        _principal_cache_invalidator=invalidator,
        _promote_existing=True,
    )

    result = use_case.execute(email="admin@example.com", password="Operator!Pa55word")

    assert isinstance(result, Ok)
    assert result.value == existing
    assert verifier.calls == [(existing, "Operator!Pa55word")]
    assert len(auth.writes) == 1
    assert auth.writes[0][0].subject_id == str(existing)
    assert invalidator.invalidated == [existing]
    assert len(audit.events) == 1
    event_type, audit_user_id, metadata = audit.events[0]
    assert event_type == "authz.system_admin_bootstrapped"
    assert audit_user_id == existing
    assert metadata is not None
    assert metadata["subevent"] == "promoted_existing"
    assert metadata["actor"] == "system"
    assert metadata["reason"] == "bootstrap_on_startup"


def test_bootstrap_refuses_promotion_when_password_mismatches() -> None:
    existing = uuid4()
    registrar = _FakeUserRegistrar(user_id=uuid4(), existing=existing)
    auth = _FakeAuthorization(check_result=False)
    audit = _FakeAudit()
    invalidator = _RecordingInvalidator()
    verifier = _RejectVerifier()
    use_case = BootstrapSystemAdmin(
        _authorization=auth,  # type: ignore[arg-type]
        _user_registrar=registrar,
        _credential_verifier=verifier,
        _audit=audit,
        _principal_cache_invalidator=invalidator,
        _promote_existing=True,
    )

    result = use_case.execute(email="admin@example.com", password="Wrong!Pa55word")

    assert isinstance(result, Err)
    err = result.error
    assert isinstance(err, BootstrapPasswordMismatchError)
    assert err.user_id == existing
    assert verifier.calls == [(existing, "Wrong!Pa55word")]
    assert auth.writes == []
    assert audit.events == []
    assert invalidator.invalidated == []


def test_bootstrap_swallows_cache_invalidation_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    user_id = uuid4()
    audit = _FakeAudit()
    error = RuntimeError("redis down")
    use_case = BootstrapSystemAdmin(
        _authorization=_FakeAuthorization(),  # type: ignore[arg-type]
        _user_registrar=_FakeUserRegistrar(user_id=user_id, existing=None),
        _credential_verifier=_NeverCalledVerifier(),
        _audit=audit,
        _principal_cache_invalidator=_RaisingInvalidator(error=error),
        _promote_existing=False,
    )

    with caplog.at_level(logging.WARNING):
        result = use_case.execute(email="admin@example.com", password="pw")

    assert isinstance(result, Ok)
    assert result.value == user_id
    # The audit event still lands — the cache failure must not roll back
    # the durable side effects.
    assert any(
        event[0] == "authz.system_admin_bootstrapped" and event[1] == user_id
        for event in audit.events
    )
    # And a WARNING log entry mentions the error reason.
    messages = [record.getMessage() for record in caplog.records]
    assert any("authz.cache_invalidation.failed" in m for m in messages)
    assert any("redis down" in m for m in messages)
