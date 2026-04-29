from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.card.patch import PatchCardCommand
from src.application.contracts import AppCard
from src.application.contracts.mappers import to_app_card, to_domain_priority
from src.application.kanban.errors import ApplicationError, from_domain_error
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.domain.shared.result import Err, Ok, Result


@dataclass(slots=True)
class PatchCardUseCase:
    uow: UnitOfWorkPort

    def execute(self, command: PatchCardCommand) -> Result[AppCard, ApplicationError]:
        if not command.has_changes():
            return Err(ApplicationError.PATCH_NO_CHANGES)

        with self.uow:
            board_id = self.uow.lookup.find_board_id_by_card(command.card_id)
            if not board_id:
                return Err(ApplicationError.CARD_NOT_FOUND)

            board_result = self.uow.commands.find_by_id(board_id)
            if isinstance(board_result, Err):
                return Err(from_domain_error(board_result.error))
            board = board_result.value

            if command.column_id is not None or command.position is not None:
                source_col = board.find_column_containing_card(command.card_id)
                if source_col:
                    target_col_id = (
                        command.column_id
                        if command.column_id is not None
                        else source_col.id
                    )
                    move_result = board.move_card(
                        command.card_id,
                        source_col.id,
                        target_col_id,
                        command.position,
                    )
                    if isinstance(move_result, Err):
                        return Err(from_domain_error(move_result.error))

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
                return Err(ApplicationError.CARD_NOT_FOUND)

            self.uow.commands.save(board)
            self.uow.commit()
            return Ok(to_app_card(updated_card))
