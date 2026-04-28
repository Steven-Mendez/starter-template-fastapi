from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoardSummary
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import AppErr, ApplicationError, AppOk, AppResult
from src.application.shared.errors import from_domain_error
from src.domain.shared.result import Err


@dataclass(frozen=True, slots=True)
class PatchBoardCommand:
    board_id: str
    title: str


def handle_patch_board(
    *,
    uow: UnitOfWorkPort,
    command: PatchBoardCommand,
) -> AppResult[AppBoardSummary, ApplicationError]:
    with uow:
        result = uow.kanban.find_by_id(command.board_id)
        if isinstance(result, Err):
            return AppErr(from_domain_error(result.error))
        board = result.value
        board.title = command.title
        uow.kanban.save(board)
        uow.commit()
        return AppOk(
            AppBoardSummary(
                id=board.id,
                title=board.title,
                created_at=board.created_at,
            )
        )
