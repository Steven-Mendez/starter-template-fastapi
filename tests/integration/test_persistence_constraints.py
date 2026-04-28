from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from src.domain.kanban.models import Board, Column
from src.domain.shared.result import Ok
from src.infrastructure.adapters.outbound.persistence.sqlmodel.repository import (
    PersistenceConflictError,
    SQLModelKanbanRepository,
)

pytestmark = pytest.mark.integration


def test_stale_board_write_returns_conflict(postgresql_dsn: str) -> None:
    repo_a = SQLModelKanbanRepository(postgresql_dsn)
    repo_b = SQLModelKanbanRepository(postgresql_dsn)
    board = Board(
        id="00000000-0000-4000-8000-000000000111",
        title="Concurrency",
        created_at=datetime.now(timezone.utc),
    )
    repo_a.save(board)

    loaded_a = repo_a.find_by_id(board.id)
    loaded_b = repo_b.find_by_id(board.id)
    assert isinstance(loaded_a, Ok)
    assert isinstance(loaded_b, Ok)

    first = loaded_a.value
    second = loaded_b.value
    first.rename("first")
    repo_a.save(first)

    second.rename("second")
    with pytest.raises(PersistenceConflictError):
        repo_b.save(second)

    repo_a.close()
    repo_b.close()


def test_position_constraints_enforced(postgresql_dsn: str) -> None:
    repo = SQLModelKanbanRepository(postgresql_dsn)
    board = Board(
        id="00000000-0000-4000-8000-000000000222",
        title="Constraints",
        created_at=datetime.now(timezone.utc),
    )
    repo.save(board)

    loaded = repo.find_by_id(board.id)
    assert isinstance(loaded, Ok)
    aggregate = loaded.value
    aggregate.add_column(
        Column(
            id="00000000-0000-4000-8000-000000000301",
            board_id=board.id,
            title="A",
            position=0,
            cards=[],
        )
    )
    aggregate.add_column(
        Column(
            id="00000000-0000-4000-8000-000000000302",
            board_id=board.id,
            title="B",
            position=0,
            cards=[],
        )
    )

    with pytest.raises(IntegrityError):
        repo.save(aggregate)

    repo.close()
