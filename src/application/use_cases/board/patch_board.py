from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.board.patch import PatchBoardCommand, handle_patch_board
from src.application.contracts import AppBoardSummary
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class PatchBoardUseCase:
    uow: UnitOfWorkPort

    def execute(
        self,
        command: PatchBoardCommand,
    ) -> AppResult[AppBoardSummary, ApplicationError]:
        return handle_patch_board(uow=self.uow, command=command)
