from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.board.create import CreateBoardCommand
from src.application.contracts import AppBoardSummary
from src.application.kanban.errors import ApplicationError
from src.application.ports.clock_port import ClockPort
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.domain.kanban.models import Board
from src.domain.shared.result import Ok, Result


@dataclass(slots=True)
class CreateBoardUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort
    clock: ClockPort

    def execute(
        self,
        command: CreateBoardCommand,
    ) -> Result[AppBoardSummary, ApplicationError]:
        board = Board(
            id=self.id_gen.next_id(),
            title=command.title,
            created_at=self.clock.now(),
        )
        with self.uow:
            self.uow.commands.save(board)
            self.uow.commit()
            return Ok(
                AppBoardSummary(
                    id=board.id,
                    title=board.title,
                    created_at=board.created_at,
                )
            )
