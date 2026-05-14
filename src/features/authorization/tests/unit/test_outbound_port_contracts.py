"""Bind the outbound-port contracts to the in-memory fake and to the real
SQLite-backed adapters.

Two contracts run against the same scenarios:

* ``UserAuthzVersionPortContract`` — exercises the bump/read-version
  probe added in ``strengthen-test-contracts``. A silent ``pass`` in
  ``bump`` no longer satisfies the contract; ``read_version`` MUST
  reflect the increment.
* ``AuditPortContract`` — asserts that recorded events are observable
  via a *separate* query, not just via the port's own write API.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from features.authentication.adapters.outbound.audit import SQLModelAuditAdapter
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
)
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authorization.tests.contracts.fake_user_authz_version import (
    FakeUserAuthzVersionPort,
)
from features.authorization.tests.contracts.outbound_port_contract import (
    AuditPortContract,
    UserAuthzVersionPortContract,
)
from features.users.adapters.outbound.authz_version import (
    SQLModelUserAuthzVersionAdapter,
)
from features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
)

pytestmark = pytest.mark.unit

_SCHEMA: list[Any] = [UserTable, AuthAuditEventTable]


def _sqlite_engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in _SCHEMA:
        table.__table__.create(engine, checkfirst=True)
    return engine


def _insert_user(engine: Engine, *, email: str = "u@example.com") -> UUID:
    with Session(engine, expire_on_commit=False) as session:
        user = UserTable(email=email)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


class _FakeAuditPort:
    """Trivial in-memory AuditPort used to exercise the contract."""

    def __init__(self) -> None:
        self.events: list[tuple[str, UUID | None, dict[str, object] | None]] = []

    def record(
        self,
        event_type: str,
        *,
        user_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.events.append((event_type, user_id, metadata))


class TestFakeUserAuthzVersionPortContract(UserAuthzVersionPortContract):
    def _make_port(self) -> FakeUserAuthzVersionPort:
        return FakeUserAuthzVersionPort()


class TestSqlmodelUserAuthzVersionPortContract(UserAuthzVersionPortContract):
    """SQLModel binding stores per-port engine state so ``read_version``
    after ``bump`` queries the row the bump just updated."""

    def _make_port(self) -> SQLModelUserAuthzVersionAdapter:
        # Stash the engine on the port instance so ``_seed_user`` can
        # reach it without an external attribute table; the adapter
        # itself is opaque to the contract base class.
        engine = _sqlite_engine()
        adapter = SQLModelUserAuthzVersionAdapter(engine)
        adapter._test_engine = engine  # type: ignore[attr-defined]
        return adapter

    def _seed_user(self, port: Any) -> UUID:
        return _insert_user(port._test_engine, email=f"{uuid4()}@example.com")


class TestFakeAuditPortContract(AuditPortContract):
    def _make_port(self) -> _FakeAuditPort:
        return _FakeAuditPort()

    def _read_events(self, port: Any) -> list[str]:
        return [event_type for event_type, _user, _meta in port.events]


class TestSqlmodelAuditPortContract(AuditPortContract):
    """Real SQLModel binding — events are read via a fresh SELECT.

    Reading from a separate ``Session`` proves the write actually
    landed in the ``auth_audit_events`` table rather than only being
    visible through the adapter's own write cursor.
    """

    def _make_port(self) -> SQLModelAuditAdapter:
        engine = _sqlite_engine()
        repo = SQLModelAuthRepository.from_engine(engine)
        adapter = SQLModelAuditAdapter(repo)
        adapter._test_engine = engine  # type: ignore[attr-defined]
        return adapter

    def _read_events(self, port: Any) -> list[str]:
        with Session(port._test_engine, expire_on_commit=False) as session:
            rows = session.exec(select(AuthAuditEventTable)).all()
        return [row.event_type for row in rows]
