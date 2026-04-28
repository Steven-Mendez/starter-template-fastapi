"""ASGI app imports only when integration tests are collected."""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

import pytest
from alembic.config import Config
from docker.errors import DockerException  # type: ignore[import-untyped]
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from alembic import command
from main import app
from src.api.dependencies import set_app_container
from src.config.settings import AppSettings
from src.infrastructure.config.di.container import build_container
from src.infrastructure.persistence.sqlmodel.models import get_sqlmodel_metadata
from tests.support.kanban_builders import ApiBuilder


@pytest.fixture
def api_client(postgresql_dsn: str) -> Generator[TestClient, None, None]:
    settings = AppSettings(
        postgresql_dsn=postgresql_dsn,
    )
    container = build_container(settings)
    with TestClient(app) as client:
        set_app_container(app, container)
        yield client
    app.dependency_overrides.clear()
    container.shutdown()


@pytest.fixture
def api_kanban(api_client: TestClient) -> ApiBuilder:
    return ApiBuilder(client=api_client)


@pytest.fixture(scope="session")
def postgresql_dsn() -> Generator[str, None, None]:
    try:
        with PostgresContainer("postgres:16-alpine") as postgres:
            dsn = _normalize_postgres_dsn(postgres.get_connection_url())
            _run_migrations(dsn)
            yield dsn
    except DockerException as exc:
        pytest.skip(f"Docker is required for PostgreSQL integration tests: {exc}")


@pytest.fixture(autouse=True)
def _clean_database(postgresql_dsn: str) -> Generator[None, None, None]:
    _truncate_kanban_tables(postgresql_dsn)
    yield


def _normalize_postgres_dsn(raw_dsn: str) -> str:
    if raw_dsn.startswith("postgresql+psycopg2://"):
        return raw_dsn.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if raw_dsn.startswith("postgresql://"):
        return raw_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_dsn


def _run_migrations(database_url: str) -> None:
    with _temporary_env_var("APP_POSTGRESQL_DSN", database_url):
        command.upgrade(Config("alembic.ini"), "head")
    _restore_application_loggers()


def _truncate_kanban_tables(database_url: str) -> None:
    table_names = [
        f'"{table.name}"' for table in reversed(get_sqlmodel_metadata().sorted_tables)
    ]
    if not table_names:
        return

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"TRUNCATE TABLE {', '.join(table_names)} "
                    "RESTART IDENTITY CASCADE"
                )
            )
    finally:
        engine.dispose()


def _restore_application_loggers() -> None:
    for logger_name in ("api.request", "api.error"):
        logging.getLogger(logger_name).disabled = False


@contextmanager
def _temporary_env_var(name: str, value: str) -> Generator[None, None, None]:
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous
