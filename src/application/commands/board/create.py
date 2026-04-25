from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoardSummary
from src.application.ports.clock import Clock
from src.application.ports.id_generator import IdGenerator
from src.application.shared import ApplicationError, AppOk, AppResult, UnitOfWork
from src.domain.kanban.models import Board


@dataclass(frozen=True, slots=True)
class CreateBoardCommand:
    title: str


def handle_create_board(
    *,
    uow: UnitOfWork,
    id_gen: IdGenerator,
    clock: Clock,
    command: CreateBoardCommand,
) -> AppResult[AppBoardSummary, ApplicationError]:
    board = Board(
        id=id_gen.next_id(),
        title=command.title,
        created_at=clock.now(),
    )
    with uow:
        uow.kanban.save(board)
        uow.commit()
        return AppOk(
            AppBoardSummary(
                id=board.id,
                title=board.title,
                created_at=board.created_at,
            )
        )
