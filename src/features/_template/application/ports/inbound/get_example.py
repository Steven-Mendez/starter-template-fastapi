from __future__ import annotations

from typing import Protocol

from src.features._template.application.errors import ApplicationError
from src.features._template.application.use_cases.get_example import GetExampleQuery
from src.features._template.domain.models.example_aggregate import ExampleAggregate
from src.platform.shared.result import Result


class GetExampleUseCasePort(Protocol):
    """Inbound contract used by adapters instead of concrete use cases."""

    def execute(
        self, query: GetExampleQuery
    ) -> Result[ExampleAggregate, ApplicationError]: ...
