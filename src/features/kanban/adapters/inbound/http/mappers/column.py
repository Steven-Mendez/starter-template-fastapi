from __future__ import annotations

from src.features.kanban.adapters.inbound.http.mappers.card import to_card_response
from src.features.kanban.adapters.inbound.http.schemas import ColumnCreate, ColumnRead
from src.features.kanban.application.contracts import AppColumn


def to_create_column_input(body: ColumnCreate) -> str:
    return body.title


def to_column_response(value: AppColumn) -> ColumnRead:
    return ColumnRead(
        id=value.id,
        board_id=value.board_id,
        title=value.title,
        position=value.position,
        cards=[to_card_response(card) for card in value.cards],
    )
