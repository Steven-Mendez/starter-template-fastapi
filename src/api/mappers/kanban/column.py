from __future__ import annotations

from src.api.mappers.kanban.card import to_card_response
from src.api.schemas.kanban import ColumnCreate, ColumnRead
from src.domain.kanban.models import Column


def to_create_column_input(body: ColumnCreate) -> str:
    return body.title


def to_column_response(value: Column) -> ColumnRead:
    return ColumnRead(
        id=value.id,
        board_id=value.board_id,
        title=value.title,
        position=value.position,
        cards=[to_card_response(card) for card in value.cards],
    )
