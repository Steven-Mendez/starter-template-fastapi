"""Unit tests for Kanban application patch board use case behavior."""

from __future__ import annotations

import pytest

from src.features.kanban.application.commands import (
    CreateBoardCommand,
    PatchBoardCommand,
)
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.use_cases.board import (
    CreateBoardUseCase,
    PatchBoardUseCase,
)
from src.features.kanban.tests.fakes import FakeKanbanWiring
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


def _seed_board(wiring: FakeKanbanWiring, title: str = "orig") -> str:
    creator = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )
    result = creator.execute(CreateBoardCommand(title=title))
    assert isinstance(result, Ok)
    return result.value.id


def test_patch_board_renames(wiring: FakeKanbanWiring) -> None:
    board_id = _seed_board(wiring)
    use_case = PatchBoardUseCase(uow=wiring.uow_factory())
    result = use_case.execute(PatchBoardCommand(board_id=board_id, title="renamed"))
    assert isinstance(result, Ok)
    assert result.value.title == "renamed"


def test_patch_board_no_changes_returns_err(wiring: FakeKanbanWiring) -> None:
    board_id = _seed_board(wiring)
    use_case = PatchBoardUseCase(uow=wiring.uow_factory())
    result = use_case.execute(PatchBoardCommand(board_id=board_id, title=None))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.PATCH_NO_CHANGES


def test_patch_board_missing_returns_not_found(wiring: FakeKanbanWiring) -> None:
    use_case = PatchBoardUseCase(uow=wiring.uow_factory())
    result = use_case.execute(PatchBoardCommand(board_id="missing", title="x"))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.BOARD_NOT_FOUND
