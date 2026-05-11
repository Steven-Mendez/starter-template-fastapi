"""Bind the outbound-port contracts to the in-memory fake and to the real
SQLite-backed adapters."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.auth.adapters.outbound.audit import SQLModelAuditAdapter
from src.features.auth.adapters.outbound.authz_version import (
    SQLModelUserAuthzVersionAdapter,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    UserTable,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.authorization.tests.contracts.fake_user_authz_version import (
    FakeUserAuthzVersionPort,
)
from src.features.authorization.tests.contracts.outbound_port_contract import (
    AuditPortContract,
    UserAuthzVersionPortContract,
)

pytestmark = pytest.mark.unit

_SCHEMA: list[Any] = [UserTable, AuthAuditEventTable]


def _sqlite_engine() -> Any:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in _SCHEMA:
        table.__table__.create(engine, checkfirst=True)
    return engine


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
    def _make_port(self) -> SQLModelUserAuthzVersionAdapter:
        return SQLModelUserAuthzVersionAdapter(_sqlite_engine())


class TestFakeAuditPortContract(AuditPortContract):
    def _make_port(self) -> _FakeAuditPort:
        return _FakeAuditPort()


class TestSqlmodelAuditPortContract(AuditPortContract):
    def _make_port(self) -> SQLModelAuditAdapter:
        repo = SQLModelAuthRepository.from_engine(_sqlite_engine())
        return SQLModelAuditAdapter(repo)
