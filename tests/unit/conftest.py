"""Unit-only fixtures for Kanban command/query setup and test builders."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from src.infrastructure.adapters.outbound.persistence.sqlmodel.models import (
    get_sqlmodel_metadata,
)
from tests.support.kanban_builders import HandlerHarness


@pytest.fixture(scope="session")
def postgresql_dsn() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        raw_dsn = postgres.get_connection_url()
        if raw_dsn.startswith("postgresql+psycopg2://"):
            yield raw_dsn.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
            return
        if raw_dsn.startswith("postgresql://"):
            yield raw_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
            return
        yield raw_dsn


@pytest.fixture(autouse=True)
def _clean_database(postgresql_dsn: str) -> None:
    engine = create_engine(postgresql_dsn, pool_pre_ping=True)
    metadata = get_sqlmodel_metadata()
    metadata.create_all(engine)
    table_names = [f'"{table.name}"' for table in reversed(metadata.sorted_tables)]
    if table_names:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE"
                )
            )
    engine.dispose()


@pytest.fixture
def handler_harness(postgresql_dsn: str) -> Generator[HandlerHarness, None, None]:
    harness = HandlerHarness.build_default(postgresql_dsn)
    try:
        yield harness
    finally:
        harness.close()
