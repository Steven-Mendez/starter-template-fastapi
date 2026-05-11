"""Bind the AuthorizationPort contract to the SQLite-backed adapter."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.auth.adapters.outbound.authorization.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    RelationshipTable,
    UserTable,
)
from src.features.auth.tests.contracts.authorization_contract import (
    AuthorizationContract,
)
from src.features.auth.tests.contracts.registry_helper import make_test_registry

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
        return SQLModelAuthorizationAdapter(engine, make_test_registry())
