"""ASGI app imports only when integration tests are collected."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dependencies import (
    build_container,
    get_kanban_command_handlers,
    get_kanban_query_handlers,
    get_kanban_repository,
    set_app_container,
)
from main import app
from settings import AppSettings


@pytest.fixture
def api_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    settings = AppSettings(
        repository_backend="sqlite",
        sqlite_path=str(tmp_path / "integration-kanban.sqlite3"),
    )
    container = build_container(settings)
    app.dependency_overrides[get_kanban_repository] = lambda: container.repository
    app.dependency_overrides[get_kanban_command_handlers] = (
        lambda: container.command_handlers
    )
    app.dependency_overrides[get_kanban_query_handlers] = (
        lambda: container.query_handlers
    )
    with TestClient(app) as client:
        set_app_container(app, container)
        yield client
    app.dependency_overrides.clear()
    container.repository.close()
