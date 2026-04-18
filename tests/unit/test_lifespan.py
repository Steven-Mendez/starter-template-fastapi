import pytest
from fastapi.testclient import TestClient

from main import app as global_app, create_app
from src.infrastructure.persistence.sqlmodel_repository import SQLModelKanbanRepository
from settings import AppSettings

pytestmark = pytest.mark.unit


def test_lifespan_closes_repository() -> None:
    settings = AppSettings(repository_backend="sqlite", sqlite_path=":memory:")
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        container = test_app.state.container
        assert container is not None
        repo = container.repository
        assert isinstance(repo, SQLModelKanbanRepository)
        assert not repo._closed

    assert repo._closed
