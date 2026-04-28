from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import AppErr, ApplicationError, AppOk, AppResult
from src.application.shared.errors import from_domain_error
from src.domain.shared.result import Err


@dataclass(frozen=True, slots=True)
class DeleteColumnCommand:
    column_id: str


def handle_delete_column(
    *,
    uow: UnitOfWorkPort,
    command: DeleteColumnCommand,
) -> AppResult[None, ApplicationError]:
    with uow:
        board_id = uow.kanban.find_board_id_by_column(command.column_id)
        if not board_id:
            return AppErr(ApplicationError.COLUMN_NOT_FOUND)

        board_result = uow.kanban.find_by_id(board_id)
        if isinstance(board_result, Err):
            return AppErr(from_domain_error(board_result.error))
        board = board_result.value

        delete_error = board.delete_column(command.column_id)
        if delete_error is not None:
            return AppErr(from_domain_error(delete_error))

        uow.kanban.save(board)
        uow.commit()
        return AppOk(None)
