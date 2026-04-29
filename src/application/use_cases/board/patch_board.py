from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.board.patch import PatchBoardCommand
from src.application.contracts import AppBoardSummary
from src.application.kanban.errors import ApplicationError, from_domain_error
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.domain.shared.result import Err, Ok, Result


@dataclass(slots=True)
class PatchBoardUseCase:
    uow: UnitOfWorkPort

    def execute(
        self,
        command: PatchBoardCommand,
    ) -> Result[AppBoardSummary, ApplicationError]:
        if not command.has_changes():
            return Err(ApplicationError.PATCH_NO_CHANGES)

        with self.uow:
            result = self.uow.commands.find_by_id(command.board_id)
            if isinstance(result, Err):
                return Err(from_domain_error(result.error))
            board = result.value
            if command.title is not None:
                board.rename(command.title)
            self.uow.commands.save(board)
            self.uow.commit()
            return Ok(
                AppBoardSummary(
                    id=board.id,
                    title=board.title,
                    created_at=board.created_at,
                )
            )
