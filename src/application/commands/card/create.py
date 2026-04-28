from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.contracts import AppCard, AppCardPriority
from src.application.contracts.mappers import to_app_card, to_domain_priority
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import AppErr, ApplicationError, AppOk, AppResult
from src.application.shared.errors import from_domain_error
from src.domain.kanban.models import Card
from src.domain.shared.result import Err


@dataclass(frozen=True, slots=True)
class CreateCardCommand:
    column_id: str
    title: str
    description: str | None
    priority: AppCardPriority
    due_at: datetime | None


def handle_create_card(
    *,
    uow: UnitOfWorkPort,
    id_gen: IdGeneratorPort,
    command: CreateCardCommand,
) -> AppResult[AppCard, ApplicationError]:
    with uow:
        board_id = uow.kanban.find_board_id_by_column(command.column_id)
        if not board_id:
            return AppErr(ApplicationError.COLUMN_NOT_FOUND)

        board_result = uow.kanban.find_by_id(board_id)
        if isinstance(board_result, Err):
            return AppErr(from_domain_error(board_result.error))
        board = board_result.value

        col = board.get_column(command.column_id)
        if not col:
            return AppErr(ApplicationError.COLUMN_NOT_FOUND)

        card = Card(
            id=id_gen.next_id(),
            column_id=command.column_id,
            title=command.title,
            description=command.description,
            position=0,  # recalculated by insert_card
            priority=to_domain_priority(command.priority),
            due_at=command.due_at,
        )
        col.insert_card(card)

        uow.kanban.save(board)
        uow.commit()
        return AppOk(to_app_card(card))
