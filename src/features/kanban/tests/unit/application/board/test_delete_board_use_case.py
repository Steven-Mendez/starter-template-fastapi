from __future__ import annotations

import pytest

from src.features.kanban.application.commands import (
    CreateBoardCommand,
    DeleteBoardCommand,
)
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.use_cases.board import (
    CreateBoardUseCase,
    DeleteBoardUseCase,
)
from src.features.kanban.tests.fakes import FakeKanbanWiring
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


def test_delete_board_removes(wiring: FakeKanbanWiring) -> None:
    creator = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )
    created = creator.execute(CreateBoardCommand(title="x"))
    assert isinstance(created, Ok)

    use_case = DeleteBoardUseCase(uow=wiring.uow_factory())
    result = use_case.execute(DeleteBoardCommand(board_id=created.value.id))
    assert isinstance(result, Ok)
    assert wiring.repository.list_all() == []


def test_delete_missing_board(wiring: FakeKanbanWiring) -> None:
    use_case = DeleteBoardUseCase(uow=wiring.uow_factory())
    result = use_case.execute(DeleteBoardCommand(board_id="missing"))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.BOARD_NOT_FOUND
