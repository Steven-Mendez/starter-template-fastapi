from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.card.patch import PatchCardCommand, handle_patch_card
from src.application.contracts import AppCard
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class PatchCardUseCase:
    uow: UnitOfWorkPort

    def execute(
        self, command: PatchCardCommand
    ) -> AppResult[AppCard, ApplicationError]:
        return handle_patch_card(uow=self.uow, command=command)
