"""Fixtures for outbox integration tests.

A real PostgreSQL is required: the relay's claim query uses
``FOR UPDATE SKIP LOCKED`` and the partial index lives in the
production schema. The session-scoped fixture starts a single
testcontainers ``postgres:16`` and drops the public schema between
tests so each one sees a clean ``outbox_messages`` table.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

# Import the table side-effect so SQLModel.metadata knows about it.
from features.outbox.adapters.outbound.sqlmodel.models import OutboxMessageTable


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


@pytest.fixture(scope="session")
def _outbox_postgres_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available for outbox testcontainers")
    container_cls = _load_postgres_container()
    assert container_cls is not None
    with container_cls("postgres:16") as pg:
        yield pg.get_connection_url().replace(
            "postgresql+psycopg2", "postgresql+psycopg"
        )


@pytest.fixture
def postgres_outbox_engine(_outbox_postgres_url: str) -> Iterator[Engine]:
    """Yield an engine with a freshly-created ``outbox_messages`` table.

    Drops and recreates the public schema between tests so each one
    starts from an empty table. The partial index lives in the
    Alembic migration; here we recreate it inline because the test
    bypasses Alembic for speed (one round-trip migration test in
    section 7.3 covers the migration itself).
    """
    engine = create_engine(_outbox_postgres_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    OutboxMessageTable.__table__.create(engine)  # type: ignore[attr-defined]
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_outbox_pending "
                "ON outbox_messages (available_at) WHERE status = 'pending'"
            )
        )
    try:
        yield engine
    finally:
        engine.dispose()
