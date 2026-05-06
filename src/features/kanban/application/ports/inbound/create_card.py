"""Inbound use-case protocol for Kanban create card operations."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.commands.card.create import CreateCardCommand
from src.features.kanban.application.contracts import AppCard
from src.features.kanban.application.errors import ApplicationError
from src.platform.shared.result import Result


class CreateCardUseCasePort(Protocol):
    """Inbound port that creates a card in a given column."""

    def execute(
        self, command: CreateCardCommand
    ) -> Result[AppCard, ApplicationError]: ...
