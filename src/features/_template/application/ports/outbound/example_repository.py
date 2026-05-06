from __future__ import annotations

from typing import Protocol

from src.features._template.domain.errors import TemplateDomainError
from src.features._template.domain.models.example_aggregate import ExampleAggregate
from src.platform.shared.result import Result


class ExampleRepositoryPort(Protocol):
    """Outbound contract implemented by infrastructure adapters."""

    def find_by_id(
        self, entity_id: str
    ) -> Result[ExampleAggregate, TemplateDomainError]: ...

    def save(self, entity: ExampleAggregate) -> None: ...
