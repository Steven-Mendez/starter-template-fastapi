from __future__ import annotations

import pytest

from src.config.settings import AppSettings
from src.infrastructure.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)
from src.infrastructure.config.di.composition import create_repository_for_settings
from src.infrastructure.config.di.container import build_container

pytestmark = pytest.mark.unit


def test_factory_selects_postgresql_repository() -> None:
    settings = AppSettings(
        postgresql_dsn="postgresql+psycopg://postgres:postgres@localhost:5432/kanban",
    )
    repository = create_repository_for_settings(settings)
    assert isinstance(repository, SQLModelKanbanRepository)
    repository.close()


def test_container_uses_postgresql_repository() -> None:
    settings = AppSettings(
        postgresql_dsn="postgresql+psycopg://postgres:postgres@localhost:5432/kanban",
    )

    container = build_container(settings)

    assert isinstance(container.repository, SQLModelKanbanRepository)
    container.shutdown()


def test_default_settings_use_local_postgresql_dsn() -> None:
    default_dsn = AppSettings.model_fields["postgresql_dsn"].default
    default_health_backend = AppSettings.model_fields[
        "health_persistence_backend"
    ].default
    assert default_dsn == "postgresql+psycopg://postgres:postgres@localhost:5432/kanban"
    assert default_health_backend == "postgresql"
