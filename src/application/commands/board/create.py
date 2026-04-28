from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoardSummary
from src.application.ports.clock_port import ClockPort
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import ApplicationError, AppOk, AppResult
from src.domain.kanban.models import Board


@dataclass(frozen=True, slots=True)
class CreateBoardCommand:
    title: str


def handle_create_board(
    *,
    uow: UnitOfWorkPort,
    id_gen: IdGeneratorPort,
    clock: ClockPort,
    command: CreateBoardCommand,
) -> AppResult[AppBoardSummary, ApplicationError]:
    board = Board(
        id=id_gen.next_id(),
        title=command.title,
        created_at=clock.now(),
    )
    with uow:
        uow.commands.save(board)
        uow.commit()
        return AppOk(
            AppBoardSummary(
                id=board.id,
                title=board.title,
                created_at=board.created_at,
            )
        )
