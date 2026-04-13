from __future__ import annotations

from pathlib import Path

import pytest

from dependencies import build_container
from kanban.repository import InMemoryKanbanRepository, create_repository_for_settings
from kanban.sqlite_repository import SQLiteKanbanRepository
from settings import AppSettings

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
    assert isinstance(repository, SQLiteKanbanRepository)
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

    sqlite_container = build_container(sqlite_settings)
    in_memory_container = build_container(in_memory_settings)

    assert isinstance(sqlite_container.repository, SQLiteKanbanRepository)
    assert isinstance(in_memory_container.repository, InMemoryKanbanRepository)
    sqlite_container.repository.close()


def test_default_settings_backend_is_sqlite() -> None:
    assert AppSettings().repository_backend == "sqlite"
