from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.contracts import AppCard, AppCardPriority
from src.application.contracts.mappers import to_app_card, to_domain_priority
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import AppErr, ApplicationError, AppOk, AppResult
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

    def has_changes(self) -> bool:
        if self.clear_due_at:
            return True
        return any(
            value is not None
            for value in (
                self.title,
                self.description,
                self.column_id,
                self.position,
                self.priority,
                self.due_at,
            )
        )


def handle_patch_card(
    *,
    uow: UnitOfWorkPort,
    command: PatchCardCommand,
) -> AppResult[AppCard, ApplicationError]:
    if not command.has_changes():
        return AppErr(ApplicationError.PATCH_NO_CHANGES)

    with uow:
        board_id = uow.kanban.find_board_id_by_card(command.card_id)
        if not board_id:
            return AppErr(ApplicationError.CARD_NOT_FOUND)

        board_result = uow.kanban.find_by_id(board_id)
        if isinstance(board_result, Err):
            return AppErr(from_domain_error(board_result.error))
        board = board_result.value

        if command.column_id is not None or command.position is not None:
            source_col = board.find_column_containing_card(command.card_id)
            if source_col:
                if command.column_id is not None:
                    target_col_id = command.column_id
                else:
                    target_col_id = source_col.id
                err = board.move_card(
                    command.card_id,
                    source_col.id,
                    target_col_id,
                    command.position,
                )
                if err:
                    return AppErr(from_domain_error(err))

        updated_card = board.get_card(command.card_id)
        if updated_card is not None:
            updated_card.apply_patch(
                title=command.title,
                description=command.description,
                priority=(
                    to_domain_priority(command.priority)
                    if command.priority is not None
                    else None
                ),
                due_at=command.due_at,
                clear_due_at=command.clear_due_at,
            )

        if not updated_card:
            return AppErr(ApplicationError.CARD_NOT_FOUND)

        uow.kanban.save(board)
        uow.commit()
        return AppOk(to_app_card(updated_card))
