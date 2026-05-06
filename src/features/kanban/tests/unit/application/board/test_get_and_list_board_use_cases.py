"""Unit tests for Kanban application get and list board use cases behavior."""

from __future__ import annotations

import pytest

from src.features.kanban.application.commands import CreateBoardCommand
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.queries import GetBoardQuery, ListBoardsQuery
from src.features.kanban.application.use_cases.board import (
    CreateBoardUseCase,
    GetBoardUseCase,
    ListBoardsUseCase,
)
from src.features.kanban.tests.fakes import FakeKanbanWiring
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


def test_get_board_returns_full_aggregate(wiring: FakeKanbanWiring) -> None:
    creator = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )
    created = creator.execute(CreateBoardCommand(title="A"))
    assert isinstance(created, Ok)

    use_case = GetBoardUseCase(query_repository=wiring.container.query_repository)
    result = use_case.execute(GetBoardQuery(board_id=created.value.id))
    assert isinstance(result, Ok)
    assert result.value.title == "A"


def test_get_board_missing(wiring: FakeKanbanWiring) -> None:
    use_case = GetBoardUseCase(query_repository=wiring.container.query_repository)
    result = use_case.execute(GetBoardQuery(board_id="missing"))
    assert isinstance(result, Err)
    assert result.error == ApplicationError.BOARD_NOT_FOUND


def test_list_boards_returns_summaries(wiring: FakeKanbanWiring) -> None:
    creator = CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    )
    creator.execute(CreateBoardCommand(title="A"))
    CreateBoardUseCase(
        uow=wiring.uow_factory(), id_gen=wiring.id_gen, clock=wiring.clock
    ).execute(CreateBoardCommand(title="B"))

    use_case = ListBoardsUseCase(query_repository=wiring.container.query_repository)
    result = use_case.execute(ListBoardsQuery())
    assert isinstance(result, Ok)
    assert sorted(s.title for s in result.value) == ["A", "B"]
