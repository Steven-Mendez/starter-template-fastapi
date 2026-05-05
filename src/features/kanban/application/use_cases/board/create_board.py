from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.commands.board.create import CreateBoardCommand
from src.features.kanban.application.contracts import AppBoardSummary
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.ports.outbound.unit_of_work import UnitOfWorkPort
from src.features.kanban.domain.models import Board
from src.platform.shared.clock_port import ClockPort
from src.platform.shared.id_generator_port import IdGeneratorPort
from src.platform.shared.result import Ok, Result


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
