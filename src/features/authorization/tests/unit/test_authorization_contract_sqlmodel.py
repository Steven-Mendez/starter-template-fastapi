"""Bind the AuthorizationPort contract to the SQLite-backed adapter."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app_platform.persistence.sqlmodel.authorization.models import RelationshipTable
from features.authorization.adapters.outbound.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from features.authorization.tests.contracts.authorization_contract import (
    AuthorizationContract,
)
from features.authorization.tests.contracts.fake_user_authz_version import (
    FakeUserAuthzVersionPort,
)
from features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)
from features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
)

pytestmark = pytest.mark.unit

_SCHEMA: list[Any] = [UserTable, RelationshipTable]


class TestSqlmodelAuthorizationContract(AuthorizationContract):
    def _make_adapter(self) -> SQLModelAuthorizationAdapter:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for table in _SCHEMA:
            table.__table__.create(engine, checkfirst=True)
        return SQLModelAuthorizationAdapter(
            engine, make_test_registry(), FakeUserAuthzVersionPort()
        )
