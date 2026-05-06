"""Pytest fixtures that spin up a real PostgreSQL container for integration tests.

The fixtures fall back to skipping when Docker is unavailable, so the
integration suite still passes on machines that cannot run
testcontainers.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

# Importing the metadata module registers all SQLModel tables on SQLModel.metadata.
import src.features.kanban.adapters.outbound.persistence.sqlmodel.models  # noqa: F401


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
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def _postgres_engine() -> Iterator[Engine]:
    if not _docker_available():
        pytest.skip("Docker not available for testcontainers")
    container_cls = _load_postgres_container()
    assert container_cls is not None
    with container_cls("postgres:16") as pg:
        url = pg.get_connection_url().replace(
            "postgresql+psycopg2", "postgresql+psycopg"
        )
        engine = create_engine(url, future=True)
        SQLModel.metadata.create_all(engine)
        yield engine
        engine.dispose()


@pytest.fixture
def postgres_engine(_postgres_engine: Engine) -> Iterator[Engine]:
    """Per-test engine that wipes all rows before each run."""
    with Session(_postgres_engine) as s:
        for table in reversed(SQLModel.metadata.sorted_tables):
            s.exec(table.delete())  # type: ignore[call-overload]
        s.commit()
    yield _postgres_engine
