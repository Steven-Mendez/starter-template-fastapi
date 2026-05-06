"""Application use case for Kanban delete board behavior."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.commands.board.delete import (
    DeleteBoardCommand,
)
from src.features.kanban.application.errors import ApplicationError, from_domain_error
from src.features.kanban.application.ports.outbound.unit_of_work import UnitOfWorkPort
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class DeleteBoardUseCase:
    uow: UnitOfWorkPort

    def execute(
        self,
        command: DeleteBoardCommand,
    ) -> Result[None, ApplicationError]:
        with self.uow:
            result = self.uow.commands.remove(command.board_id)
            if isinstance(result, Err):
                return Err(from_domain_error(result.error))
            self.uow.commit()
            return Ok(None)
