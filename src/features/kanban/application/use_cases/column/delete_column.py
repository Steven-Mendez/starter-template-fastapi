"""Application use case for Kanban delete column behavior."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.commands.column.delete import (
    DeleteColumnCommand,
)
from src.features.kanban.application.errors import ApplicationError, from_domain_error
from src.features.kanban.application.ports.outbound.unit_of_work import UnitOfWorkPort
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class DeleteColumnUseCase:
    uow: UnitOfWorkPort

    def execute(self, command: DeleteColumnCommand) -> Result[None, ApplicationError]:
        with self.uow:
            board_id = self.uow.lookup.find_board_id_by_column(command.column_id)
            if not board_id:
                return Err(ApplicationError.COLUMN_NOT_FOUND)

            board_result = self.uow.commands.find_by_id(board_id)
            if isinstance(board_result, Err):
                return Err(from_domain_error(board_result.error))
            board = board_result.value

            delete_result = board.delete_column(command.column_id)
            if isinstance(delete_result, Err):
                return Err(from_domain_error(delete_result.error))

            self.uow.commands.save(board)
            self.uow.commit()
            return Ok(None)
