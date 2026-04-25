from __future__ import annotations

from dataclasses import dataclass

from src.application.shared import AppErr, ApplicationError, AppOk, AppResult, UnitOfWork
from src.application.shared.errors import from_domain_error
from src.domain.shared.result import Err


@dataclass(frozen=True, slots=True)
class DeleteBoardCommand:
    board_id: str


def handle_delete_board(
    *,
    uow: UnitOfWork,
    command: DeleteBoardCommand,
) -> AppResult[None, ApplicationError]:
    with uow:
        result = uow.kanban.remove(command.board_id)
        if isinstance(result, Err):
            return AppErr(from_domain_error(result.error))
        uow.commit()
        return AppOk(None)
