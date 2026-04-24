"""ASGI app imports only when integration tests are collected."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from src.api.dependencies import set_app_container
from src.config.settings import AppSettings
from src.infrastructure.config.di.container import build_container
from tests.support.kanban_builders import ApiBuilder


@pytest.fixture
def api_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    settings = AppSettings(
        repository_backend="sqlite",
        sqlite_path=str(tmp_path / "integration-kanban.sqlite3"),
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
