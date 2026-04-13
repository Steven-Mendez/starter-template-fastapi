"""ASGI app imports only when integration tests are collected."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kanban.store import KanbanStore, get_store
from main import app


@pytest.fixture
def api_client(kanban_store: KanbanStore) -> TestClient:
    app.dependency_overrides[get_store] = lambda: kanban_store
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
