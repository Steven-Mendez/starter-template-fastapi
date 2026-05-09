"""Domain models reject naive datetimes at construction."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.features.kanban.domain.models import (
    Board,
    BoardSummary,
    Card,
    CardPriority,
)

pytestmark = pytest.mark.unit


def test_board_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="Board.created_at"):
        Board(id="b1", title="t", created_at=datetime(2026, 1, 1))


def test_board_accepts_aware_created_at() -> None:
    Board(id="b1", title="t", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_board_summary_rejects_naive() -> None:
    with pytest.raises(ValueError, match="BoardSummary.created_at"):
        BoardSummary(id="b1", title="t", created_at=datetime(2026, 1, 1))


def test_card_rejects_naive_due_at() -> None:
    with pytest.raises(ValueError, match="Card.due_at"):
        Card(
            id="k1",
            column_id="c1",
            title="t",
            description=None,
            position=0,
            priority=CardPriority.MEDIUM,
            due_at=datetime(2026, 1, 1),
        )


def test_card_accepts_no_due_at() -> None:
    Card(
        id="k1",
        column_id="c1",
        title="t",
        description=None,
        position=0,
        priority=CardPriority.MEDIUM,
        due_at=None,
    )
