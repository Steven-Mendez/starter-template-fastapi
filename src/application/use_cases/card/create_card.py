from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.card.create import CreateCardCommand
from src.application.contracts import AppCard
from src.application.contracts.mappers import to_app_card, to_domain_priority
from src.application.kanban.errors import ApplicationError, from_domain_error
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.domain.kanban.models import Card
from src.domain.shared.result import Err, Ok, Result


@dataclass(slots=True)
class CreateCardUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort

    def execute(self, command: CreateCardCommand) -> Result[AppCard, ApplicationError]:
        with self.uow:
            board_id = self.uow.lookup.find_board_id_by_column(command.column_id)
            if not board_id:
                return Err(ApplicationError.COLUMN_NOT_FOUND)

            board_result = self.uow.commands.find_by_id(board_id)
            if isinstance(board_result, Err):
                return Err(from_domain_error(board_result.error))
            board = board_result.value

            col = board.get_column(command.column_id)
            if not col:
                return Err(ApplicationError.COLUMN_NOT_FOUND)

            card = Card(
                id=self.id_gen.next_id(),
                column_id=command.column_id,
                title=command.title,
                description=command.description,
                position=0,
                priority=to_domain_priority(command.priority),
                due_at=command.due_at,
            )
            col.insert_card(card)

            self.uow.commands.save(board)
            self.uow.commit()
            return Ok(to_app_card(card))
