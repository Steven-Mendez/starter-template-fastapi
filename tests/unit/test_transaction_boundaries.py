from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.domain.kanban.models import Board
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, expect_ok
from src.infrastructure.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)
from src.infrastructure.adapters.outbound.persistence.sqlmodel.unit_of_work import (
    SqlModelUnitOfWork,
)

pytestmark = pytest.mark.unit


def _new_board(title: str) -> Board:
    return Board(
        id=str(uuid.uuid4()),
        title=title,
        created_at=datetime.now(timezone.utc),
        columns=[],
    )


def test_uow_save_requires_explicit_commit(postgresql_dsn: str) -> None:
    repository = SQLModelKanbanRepository(postgresql_dsn)
    try:
        board = _new_board("Original")
        repository.save(board)

        with SqlModelUnitOfWork(repository.engine) as uow:
            loaded = expect_ok(uow.commands.find_by_id(board.id))
            loaded.title = "Changed"
            uow.commands.save(loaded)

        refreshed = expect_ok(repository.find_by_id(board.id))
        assert refreshed.title == "Original"
    finally:
        repository.close()


def test_uow_remove_requires_explicit_commit(postgresql_dsn: str) -> None:
    repository = SQLModelKanbanRepository(postgresql_dsn)
    try:
        board = _new_board("To remove")
        repository.save(board)

        with SqlModelUnitOfWork(repository.engine) as uow:
            removed = uow.commands.remove(board.id)
            assert not isinstance(removed, Err)

        still_there = expect_ok(repository.find_by_id(board.id))
        assert still_there.id == board.id
    finally:
        repository.close()


def test_uow_commit_persists_writes(postgresql_dsn: str) -> None:
    repository = SQLModelKanbanRepository(postgresql_dsn)
    try:
        board = _new_board("Committed")

        with SqlModelUnitOfWork(repository.engine) as uow:
            uow.commands.save(board)
            uow.commit()

        persisted = expect_ok(repository.find_by_id(board.id))
        assert persisted.id == board.id
    finally:
        repository.close()


def test_uow_rolls_back_on_exception(postgresql_dsn: str) -> None:
    repository = SQLModelKanbanRepository(postgresql_dsn)
    try:
        board = _new_board("Rollback")

        with pytest.raises(RuntimeError, match="boom"):
            with SqlModelUnitOfWork(repository.engine) as uow:
                uow.commands.save(board)
                raise RuntimeError("boom")

        result = repository.find_by_id(board.id)
        assert isinstance(result, Err)
        assert result.error is KanbanError.BOARD_NOT_FOUND
    finally:
        repository.close()
