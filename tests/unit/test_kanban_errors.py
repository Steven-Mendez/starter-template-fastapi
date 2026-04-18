from __future__ import annotations

import pytest

from src.domain.shared.errors import KanbanError

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (KanbanError.BOARD_NOT_FOUND, "Board not found"),
        (KanbanError.COLUMN_NOT_FOUND, "Column not found"),
        (KanbanError.CARD_NOT_FOUND, "Card not found"),
        (KanbanError.INVALID_CARD_MOVE, "Invalid card move"),
    ],
)
def test_kanban_error_details_are_stable(error: KanbanError, detail: str) -> None:
    assert error.detail == detail
