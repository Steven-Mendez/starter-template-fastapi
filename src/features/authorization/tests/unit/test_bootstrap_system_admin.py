"""Unit tests for ``BootstrapSystemAdmin``.

Covers the cache-invalidation path added by
``make-authz-grant-atomic``: a successful grant invalidates the
principal cache for the bootstrapped user, and a cache failure is
logged and swallowed so the DB-side success is not undone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from features.authorization.application.types import Relationship
from features.authorization.application.use_cases import BootstrapSystemAdmin

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class _FakeUserRegistrar:
    """Returns a fixed user id and records the credentials it was called with."""

    user_id: UUID
    calls: list[tuple[str, str]] = field(default_factory=list)

    def register_or_lookup(self, *, email: str, password: str) -> UUID:
        self.calls.append((email, password))
        return self.user_id


@dataclass(slots=True)
class _FakeAuthorization:
    """Records every ``write_relationships`` call."""

    writes: list[list[Relationship]] = field(default_factory=list)

    def write_relationships(self, tuples: list[Relationship]) -> None:
        self.writes.append(list(tuples))

    # The other ``AuthorizationPort`` methods are not exercised by the
    # bootstrap use case; ``BootstrapSystemAdmin`` only writes.


@dataclass(slots=True)
class _FakeAudit:
    """Captures audit events for assertions."""

    events: list[tuple[str, UUID | None]] = field(default_factory=list)

    def record(
        self,
        event_type: str,
        *,
        user_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        del metadata
        self.events.append((event_type, user_id))


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


def test_bootstrap_invalidates_principal_cache_on_success() -> None:
    user_id = uuid4()
    invalidator = _RecordingInvalidator()
    use_case = BootstrapSystemAdmin(
        _authorization=_FakeAuthorization(),  # type: ignore[arg-type]
        _user_registrar=_FakeUserRegistrar(user_id=user_id),
        _audit=_FakeAudit(),
        _principal_cache_invalidator=invalidator,
    )

    returned = use_case.execute(email="admin@example.com", password="pw")

    assert returned == user_id
    assert invalidator.invalidated == [user_id]


def test_bootstrap_swallows_cache_invalidation_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    user_id = uuid4()
    audit = _FakeAudit()
    error = RuntimeError("redis down")
    use_case = BootstrapSystemAdmin(
        _authorization=_FakeAuthorization(),  # type: ignore[arg-type]
        _user_registrar=_FakeUserRegistrar(user_id=user_id),
        _audit=audit,
        _principal_cache_invalidator=_RaisingInvalidator(error=error),
    )

    with caplog.at_level(logging.WARNING):
        returned = use_case.execute(email="admin@example.com", password="pw")

    assert returned == user_id
    # The audit event still lands — the cache failure must not roll back
    # the durable side effects.
    assert ("authz.bootstrap_admin_assigned", user_id) in audit.events
    # And a WARNING log entry mentions the error reason.
    messages = [record.getMessage() for record in caplog.records]
    assert any("authz.cache_invalidation.failed" in m for m in messages)
    assert any("redis down" in m for m in messages)
