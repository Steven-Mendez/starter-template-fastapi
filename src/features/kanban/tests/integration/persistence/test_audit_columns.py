"""Integration tests for the kanban created_by / updated_by audit columns."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Engine

from src.features.kanban.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)
from src.features.kanban.domain.models import Board

pytestmark = pytest.mark.integration


def _board(*, board_id: str, created_by: UUID | None, updated_by: UUID | None) -> Board:
    return Board(
        id=board_id,
        title="Roadmap",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_by=created_by,
        updated_by=updated_by,
    )


def test_create_persists_actor_in_both_columns(postgres_engine: Engine) -> None:
    repo = SQLModelKanbanRepository.from_engine(postgres_engine)
    actor_a = uuid4()
    repo.save(_board(board_id="b-1", created_by=actor_a, updated_by=actor_a))

    found = repo.find_by_id("b-1")
    assert found.value.created_by == actor_a  # type: ignore[union-attr]
    assert found.value.updated_by == actor_a  # type: ignore[union-attr]


def test_update_changes_only_updated_by(postgres_engine: Engine) -> None:
    repo = SQLModelKanbanRepository.from_engine(postgres_engine)
    creator = uuid4()
    editor = uuid4()
    repo.save(_board(board_id="b-2", created_by=creator, updated_by=creator))

    loaded = repo.find_by_id("b-2").value  # type: ignore[union-attr]
    loaded.updated_by = editor
    repo.save(loaded)

    refreshed = repo.find_by_id("b-2").value  # type: ignore[union-attr]
    assert refreshed.created_by == creator
    assert refreshed.updated_by == editor


def test_anonymous_writes_leave_columns_null(postgres_engine: Engine) -> None:
    repo = SQLModelKanbanRepository.from_engine(postgres_engine)
    repo.save(_board(board_id="b-3", created_by=None, updated_by=None))
    found = repo.find_by_id("b-3").value  # type: ignore[union-attr]
    assert found.created_by is None
    assert found.updated_by is None
