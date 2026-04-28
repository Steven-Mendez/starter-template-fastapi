from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.board.delete import (
    DeleteBoardCommand,
    handle_delete_board,
)
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class DeleteBoardUseCase:
    uow: UnitOfWorkPort

    def execute(
        self,
        command: DeleteBoardCommand,
    ) -> AppResult[None, ApplicationError]:
        return handle_delete_board(uow=self.uow, command=command)
