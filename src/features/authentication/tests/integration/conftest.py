"""Fixtures for auth integration tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app_platform.persistence.sqlmodel.authorization.models import RelationshipTable
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    CredentialTable,
    RefreshTokenTable,
)
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (  # noqa: E501
    SQLModelAuthRepository,
)
from features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
)
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)

AUTH_TABLES: list[Any] = [
    UserTable,
    RelationshipTable,
    CredentialTable,
    RefreshTokenTable,
    AuthAuditEventTable,
    AuthInternalTokenTable,
]


def _load_postgres_container() -> Any:
    try:
        from testcontainers.postgres import (  # type: ignore[import-untyped]
            PostgresContainer,
        )
    except Exception:
        return None
    return PostgresContainer


def _docker_available() -> bool:
    if _load_postgres_container() is None:
        return False
    if os.environ.get("AUTH_SKIP_TESTCONTAINERS") == "1":
        return False
    try:
        import docker  # type: ignore[import-untyped]

        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.fixture
def users_for_auth(
    sqlite_auth_repository: SQLModelAuthRepository,
) -> SQLModelUserRepository:
    """``UserPort`` implementation sharing the in-memory SQLite engine."""
    return SQLModelUserRepository(engine=sqlite_auth_repository.engine)


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


@pytest.fixture(scope="session")
def _auth_postgres_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available for auth testcontainers")
    container_cls = _load_postgres_container()
    assert container_cls is not None
    with container_cls("postgres:16") as pg:
        yield pg.get_connection_url().replace(
            "postgresql+psycopg2", "postgresql+psycopg"
        )


@pytest.fixture
def postgres_auth_repository(
    _auth_postgres_url: str,
) -> Iterator[SQLModelAuthRepository]:
    """PostgreSQL-backed auth repository for row-locking integration tests.

    The session-scoped postgres container is shared across tests, and the
    migration round-trip suite can leave the schema at an arbitrary
    historical revision. Drop ``public`` before invoking ``create_all`` so
    every test sees the same fresh schema regardless of what ran before.
    """
    _reset_public_schema(_auth_postgres_url)
    repository = SQLModelAuthRepository(_auth_postgres_url, create_schema=True)
    try:
        yield repository
    finally:
        repository.close()


def _reset_public_schema(url: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()
