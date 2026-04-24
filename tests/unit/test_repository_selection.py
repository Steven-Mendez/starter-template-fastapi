from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import AppSettings
from src.infrastructure.config.di.composition import create_repository_for_settings
from src.infrastructure.config.di.container import build_container
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository
from src.infrastructure.persistence.sqlmodel_repository import SQLModelKanbanRepository

pytestmark = pytest.mark.unit


def test_factory_selects_inmemory_repository() -> None:
    settings = AppSettings(
        repository_backend="inmemory",
        sqlite_path=".data/unused.db",
    )
    repository = create_repository_for_settings(settings)
    assert isinstance(repository, InMemoryKanbanRepository)


def test_factory_selects_sqlite_repository(tmp_path: Path) -> None:
    settings = AppSettings(
        repository_backend="sqlite",
        sqlite_path=str(tmp_path / "factory-select.sqlite3"),
    )
    repository = create_repository_for_settings(settings)
    assert isinstance(repository, SQLModelKanbanRepository)
    repository.close()


def test_factory_selects_postgresql_repository() -> None:
    settings = AppSettings(
        repository_backend="postgresql",
        postgresql_dsn="postgresql+psycopg://postgres:postgres@localhost:5432/kanban",
    )
    repository = create_repository_for_settings(settings)
    assert isinstance(repository, SQLModelKanbanRepository)
    repository.close()


def test_container_uses_selected_repository_backend(tmp_path: Path) -> None:
    sqlite_settings = AppSettings(
        repository_backend="sqlite",
        sqlite_path=str(tmp_path / "container.sqlite3"),
    )
    in_memory_settings = AppSettings(
        repository_backend="inmemory",
        sqlite_path=str(tmp_path / "unused.sqlite3"),
    )
    postgresql_settings = AppSettings(
        repository_backend="postgresql",
        postgresql_dsn="postgresql+psycopg://postgres:postgres@localhost:5432/kanban",
    )

    sqlite_container = build_container(sqlite_settings)
    in_memory_container = build_container(in_memory_settings)
    postgresql_container = build_container(postgresql_settings)

    assert isinstance(sqlite_container.repository, SQLModelKanbanRepository)
    assert isinstance(in_memory_container.repository, InMemoryKanbanRepository)
    assert isinstance(postgresql_container.repository, SQLModelKanbanRepository)
    sqlite_container.shutdown()
    in_memory_container.shutdown()
    postgresql_container.shutdown()


def test_default_settings_backend_is_postgresql() -> None:
    default_backend = AppSettings.model_fields["repository_backend"].default
    assert default_backend == "postgresql"
