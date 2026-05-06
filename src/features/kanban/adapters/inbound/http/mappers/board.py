"""Transport-to-application mappers for board payloads."""

from __future__ import annotations

from src.features.kanban.adapters.inbound.http.mappers.column import to_column_response
from src.features.kanban.adapters.inbound.http.schemas import (
    BoardCreate,
    BoardDetail,
    BoardSummary,
    BoardUpdate,
)
from src.features.kanban.application.contracts import AppBoard, AppBoardSummary


def to_create_board_input(body: BoardCreate) -> str:
    """Pull the title out of an inbound :class:`BoardCreate` payload."""
    return body.title


def to_patch_board_input(body: BoardUpdate) -> str | None:
    """Return the optional title from an inbound :class:`BoardUpdate` payload."""
    return body.title


def to_board_summary_response(value: AppBoardSummary) -> BoardSummary:
    """Project an :class:`AppBoardSummary` into the public HTTP shape."""
    return BoardSummary(id=value.id, title=value.title, created_at=value.created_at)


def to_board_detail_response(value: AppBoard) -> BoardDetail:
    """Project a full :class:`AppBoard` with columns and cards into HTTP."""
    return BoardDetail(
        id=value.id,
        title=value.title,
        created_at=value.created_at,
        columns=[to_column_response(column) for column in value.columns],
    )
