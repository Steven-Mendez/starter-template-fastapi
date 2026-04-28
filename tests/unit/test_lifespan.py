import pytest
from fastapi.testclient import TestClient

from main import create_app
from src.config.settings import AppSettings
from src.infrastructure.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)

pytestmark = pytest.mark.unit


def test_lifespan_closes_repository(postgresql_dsn: str) -> None:
    settings = AppSettings(postgresql_dsn=postgresql_dsn)
    test_app = create_app(settings)

    with TestClient(test_app):
        container = test_app.state.container
        assert container is not None
        repo = container.repository
        assert isinstance(repo, SQLModelKanbanRepository)
        assert repo.is_ready()

    assert not repo.is_ready()
