from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.contracts import AppCard, AppCardPriority
from src.application.contracts.mappers import to_app_card, to_domain_priority
from src.application.shared import AppErr, ApplicationError, AppOk, AppResult, UnitOfWork
from src.application.shared.errors import from_domain_error
from src.domain.shared.result import Err


@dataclass(frozen=True, slots=True)
class PatchCardCommand:
    card_id: str
    title: str | None = None
    description: str | None = None
    column_id: str | None = None
    position: int | None = None
    priority: AppCardPriority | None = None
    due_at: datetime | None = None
    clear_due_at: bool = False


def handle_patch_card(
    *,
    uow: UnitOfWork,
    command: PatchCardCommand,
) -> AppResult[AppCard, ApplicationError]:
    with uow:
        board_id = uow.kanban.find_board_id_by_card(command.card_id)
        if not board_id:
            return AppErr(ApplicationError.CARD_NOT_FOUND)

        board_result = uow.kanban.find_by_id(board_id)
        if isinstance(board_result, Err):
            return AppErr(from_domain_error(board_result.error))
        board = board_result.value

        if command.column_id is not None or command.position is not None:
            source_col = next(
                (
                    c
                    for c in board.columns
                    if any(ca.id == command.card_id for ca in c.cards)
                ),
                None,
            )
            if source_col:
                target_col_id = (
                    command.column_id if command.column_id is not None else source_col.id
                )
                err = board.move_card(
                    command.card_id,
                    source_col.id,
                    target_col_id,
                    command.position,
                )
                if err:
                    return AppErr(from_domain_error(err))

        updated_card = None
        for col in board.columns:
            for card in col.cards:
                if card.id == command.card_id:
                    if command.title is not None:
                        card.title = command.title
                    if command.description is not None:
                        card.description = command.description
                    if command.priority is not None:
                        card.priority = to_domain_priority(command.priority)
                    if command.clear_due_at or command.due_at is not None:
                        card.due_at = command.due_at
                    updated_card = card
                    break

        if not updated_card:
            return AppErr(ApplicationError.CARD_NOT_FOUND)

        uow.kanban.save(board)
        uow.commit()
        return AppOk(to_app_card(updated_card))
