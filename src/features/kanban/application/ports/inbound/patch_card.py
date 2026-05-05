from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.commands.card.patch import PatchCardCommand
from src.features.kanban.application.contracts import AppCard
from src.features.kanban.application.errors import ApplicationError
from src.platform.shared.result import Result


class PatchCardUseCasePort(Protocol):
    def execute(
        self, command: PatchCardCommand
    ) -> Result[AppCard, ApplicationError]: ...
