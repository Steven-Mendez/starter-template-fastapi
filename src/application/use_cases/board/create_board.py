from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.board.create import (
    CreateBoardCommand,
    handle_create_board,
)
from src.application.contracts import AppBoardSummary
from src.application.ports.clock_port import ClockPort
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class CreateBoardUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort
    clock: ClockPort

    def execute(
        self,
        command: CreateBoardCommand,
    ) -> AppResult[AppBoardSummary, ApplicationError]:
        return handle_create_board(
            uow=self.uow,
            id_gen=self.id_gen,
            clock=self.clock,
            command=command,
        )
