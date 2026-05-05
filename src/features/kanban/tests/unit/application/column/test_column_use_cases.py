from __future__ import annotations

import pytest

from src.features.kanban.application.commands import (
    CreateBoardCommand,
    CreateColumnCommand,
    DeleteColumnCommand,
)
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.use_cases.board import CreateBoardUseCase
from src.features.kanban.application.use_cases.column import (
    CreateColumnUseCase,
    DeleteColumnUseCase,
)
from src.features.kanban.tests.fakes import FakeKanbanWiring
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


def _make_board(wiring: FakeKanbanWiring) -> str:
    creator = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )
    created = creator.execute(CreateBoardCommand(title="b"))
    assert isinstance(created, Ok)
    return created.value.id


def test_create_column_succeeds(wiring: FakeKanbanWiring) -> None:
    board_id = _make_board(wiring)
    use_case = CreateColumnUseCase(uow=wiring.uow_factory(), id_gen=wiring.id_gen)
    result = use_case.execute(CreateColumnCommand(board_id=board_id, title="To Do"))
    assert isinstance(result, Ok)
    assert result.value.title == "To Do"
    assert result.value.position == 0


def test_create_column_board_missing(wiring: FakeKanbanWiring) -> None:
    use_case = CreateColumnUseCase(uow=wiring.uow_factory(), id_gen=wiring.id_gen)
    result = use_case.execute(CreateColumnCommand(board_id="missing", title="To Do"))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.BOARD_NOT_FOUND


def test_delete_column_succeeds(wiring: FakeKanbanWiring) -> None:
    board_id = _make_board(wiring)
    create = CreateColumnUseCase(uow=wiring.uow_factory(), id_gen=wiring.id_gen)
    created = create.execute(CreateColumnCommand(board_id=board_id, title="x"))
    assert isinstance(created, Ok)

    use_case = DeleteColumnUseCase(uow=wiring.uow_factory())
    result = use_case.execute(DeleteColumnCommand(column_id=created.value.id))
    assert isinstance(result, Ok)


def test_delete_column_missing(wiring: FakeKanbanWiring) -> None:
    use_case = DeleteColumnUseCase(uow=wiring.uow_factory())
    result = use_case.execute(DeleteColumnCommand(column_id="missing"))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.COLUMN_NOT_FOUND
