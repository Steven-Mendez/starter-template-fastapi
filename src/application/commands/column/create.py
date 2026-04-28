from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppColumn
from src.application.contracts.mappers import to_app_column
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import AppErr, ApplicationError, AppOk, AppResult
from src.application.shared.errors import from_domain_error
from src.domain.kanban.models import Column
from src.domain.shared.result import Err


@dataclass(frozen=True, slots=True)
class CreateColumnCommand:
    board_id: str
    title: str


def handle_create_column(
    *,
    uow: UnitOfWorkPort,
    id_gen: IdGeneratorPort,
    command: CreateColumnCommand,
) -> AppResult[AppColumn, ApplicationError]:
    with uow:
        board_result = uow.commands.find_by_id(command.board_id)
        if isinstance(board_result, Err):
            return AppErr(from_domain_error(board_result.error))
        board = board_result.value

        column = Column(
            id=id_gen.next_id(),
            board_id=command.board_id,
            title=command.title,
            position=board.next_column_position(),
        )
        board.add_column(column)

        uow.commands.save(board)
        uow.commit()
        return AppOk(to_app_column(column))
