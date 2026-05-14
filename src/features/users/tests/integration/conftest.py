"""Fixtures for users-feature integration tests.

A real PostgreSQL is required so the outbox relay's
``FOR UPDATE SKIP LOCKED`` claim query has the production semantics
this suite asserts against. The session-scoped fixture starts a single
``postgres:16`` testcontainer and drops the public schema between
tests so each one sees a fresh ``outbox_messages`` + ``users`` table.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

# Import the table side-effects so ``SQLModel.metadata`` knows about them.
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    CredentialTable,
    RefreshTokenTable,
)
from features.outbox.adapters.outbound.sqlmodel.models import (
    OutboxMessageTable,
    ProcessedOutboxMessageTable,
)
from features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
)

_TABLES: list[Any] = [
    UserTable,
    # Auth tables — required for the GDPR erasure integration tests
    # that assert auth_audit_events scrub + credential/refresh-token
    # deletion happen atomically with the user-row scrub.
    CredentialTable,
    RefreshTokenTable,
    AuthAuditEventTable,
    AuthInternalTokenTable,
    OutboxMessageTable,
    ProcessedOutboxMessageTable,
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
    if os.environ.get("KANBAN_SKIP_TESTCONTAINERS") == "1":
        return False
    try:
        import docker  # type: ignore[import-untyped]

        docker.from_env().ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="session")
def _users_postgres_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available for users-integration testcontainers")
    container_cls = _load_postgres_container()
    assert container_cls is not None
    with container_cls("postgres:16") as pg:
        yield pg.get_connection_url().replace(
            "postgresql+psycopg2", "postgresql+psycopg"
        )


@pytest.fixture
def postgres_users_engine(_users_postgres_url: str) -> Iterator[Engine]:
    """Engine with a freshly-created ``users`` + ``outbox_messages`` schema."""
    engine = create_engine(_users_postgres_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    for table in _TABLES:
        table.__table__.create(engine)
    with engine.begin() as conn:
        # Match the production partial-index shape so the relay's
        # ``ORDER BY (available_at, id)`` is fully determined.
        conn.execute(text("DROP INDEX IF EXISTS ix_outbox_pending"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_outbox_pending "
                "ON outbox_messages (available_at, id) "
                "WHERE status = 'pending'"
            )
        )
    try:
        yield engine
    finally:
        engine.dispose()
