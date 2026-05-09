"""Readiness probe tests for migration-state validation."""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.kanban.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)

pytestmark = pytest.mark.unit


def test_readiness_fails_when_alembic_version_table_is_missing() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SQLModelKanbanRepository.from_engine(engine, create_schema=False)

    try:
        assert repository.is_ready() is False
    finally:
        repository.close()
