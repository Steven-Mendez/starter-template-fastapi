"""ASGI app imports only when integration tests are collected."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dependencies import get_kanban_repository
from kanban.repository import KanbanRepository
from kanban.sqlite_repository import SQLiteKanbanRepository
from main import app


@pytest.fixture
def api_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    repo: KanbanRepository = SQLiteKanbanRepository(
        str(tmp_path / "integration-kanban.sqlite3")
    )
    app.dependency_overrides[get_kanban_repository] = lambda: repo
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
