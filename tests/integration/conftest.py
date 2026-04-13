"""ASGI app imports only when integration tests are collected."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from dependencies import get_kanban_repository
from kanban.store import KanbanStore
from main import app


@pytest.fixture
def api_client(kanban_store: KanbanStore) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_kanban_repository] = lambda: kanban_store
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
