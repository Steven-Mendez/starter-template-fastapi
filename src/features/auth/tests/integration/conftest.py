"""Fixtures for auth integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    PermissionTable,
    RefreshTokenTable,
    RolePermissionTable,
    RoleTable,
    UserRoleTable,
    UserTable,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)

AUTH_TABLES: list[Any] = [
    UserTable,
    RoleTable,
    PermissionTable,
    UserRoleTable,
    RolePermissionTable,
    RefreshTokenTable,
    AuthAuditEventTable,
    AuthInternalTokenTable,
]


@pytest.fixture
def sqlite_auth_repository() -> Iterator[SQLModelAuthRepository]:
    """SQLite in-memory repository with the auth schema (same shape as e2e)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in AUTH_TABLES:
        table.__table__.create(engine, checkfirst=True)
    repository = SQLModelAuthRepository.from_engine(engine)
    try:
        yield repository
    finally:
        repository.close()
