from __future__ import annotations

import pytest

from src.application.commands import (
    CreateBoardCommand,
    CreateCardCommand,
    CreateColumnCommand,
    KanbanCommandHandlers,
)
from src.application.queries import GetBoardQuery, KanbanQueryHandlers
from src.domain.kanban.models import CardPriority
from src.domain.shared.result import Ok
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository

pytestmark = pytest.mark.unit


def test_command_handlers_only_expose_mutations() -> None:
    commands = KanbanCommandHandlers(repository=InMemoryKanbanRepository())
    assert hasattr(commands, "handle_create_board")
    assert hasattr(commands, "handle_patch_card")
    assert not hasattr(commands, "handle_get_board")
    assert not hasattr(commands, "handle_list_boards")


def test_query_handlers_only_expose_reads() -> None:
    queries = KanbanQueryHandlers(repository=InMemoryKanbanRepository())
    assert hasattr(queries, "handle_list_boards")
    assert hasattr(queries, "handle_get_card")
    assert not hasattr(queries, "handle_create_board")
    assert not hasattr(queries, "handle_patch_card")


def test_router_use_case_can_be_done_with_split_handlers() -> None:
    repository = InMemoryKanbanRepository()
    commands = KanbanCommandHandlers(repository=repository)
    queries = KanbanQueryHandlers(repository=repository)

    board = commands.handle_create_board(CreateBoardCommand(title="Roadmap"))
    created_column = commands.handle_create_column(
        CreateColumnCommand(board_id=board.id, title="Todo")
    )
    assert isinstance(created_column, Ok)
    created_card = commands.handle_create_card(
        CreateCardCommand(
            column_id=created_column.value.id,
            title="Task A",
            description=None,
            priority=CardPriority.MEDIUM,
            due_at=None,
        )
    )
    assert isinstance(created_card, Ok)

    fetched_board = queries.handle_get_board(GetBoardQuery(board_id=board.id))
    assert isinstance(fetched_board, Ok)
    assert fetched_board.value.columns[0].cards[0].id == created_card.value.id
