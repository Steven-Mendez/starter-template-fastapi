from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.card.create import CreateCardCommand, handle_create_card
from src.application.contracts import AppCard
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class CreateCardUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort

    def execute(
        self, command: CreateCardCommand
    ) -> AppResult[AppCard, ApplicationError]:
        return handle_create_card(uow=self.uow, id_gen=self.id_gen, command=command)
