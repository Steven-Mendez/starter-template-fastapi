from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.contracts import AppCard
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.queries.get_card import GetCardQuery
from src.platform.shared.result import Result


class GetCardUseCasePort(Protocol):
    def execute(self, query: GetCardQuery) -> Result[AppCard, ApplicationError]: ...
