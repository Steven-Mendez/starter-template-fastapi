from __future__ import annotations

from src.api.mappers.kanban.column import to_column_response
from src.api.schemas.kanban import (
    BoardCreate,
    BoardDetail,
    BoardSummary,
    BoardUpdate,
)
from src.domain.kanban.models import Board
from src.domain.kanban.models import BoardSummary as DomainBoardSummary


def to_create_board_input(body: BoardCreate) -> str:
    return body.title


def to_patch_board_input(body: BoardUpdate) -> str | None:
    return body.title


def to_board_summary_response(value: DomainBoardSummary) -> BoardSummary:
    return BoardSummary(id=value.id, title=value.title, created_at=value.created_at)


def to_board_detail_response(value: Board) -> BoardDetail:
    return BoardDetail(
        id=value.id,
        title=value.title,
        created_at=value.created_at,
        columns=[to_column_response(column) for column in value.columns],
    )
