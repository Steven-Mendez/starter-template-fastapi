from __future__ import annotations

# TODO(template): replace this in-memory adapter with a real implementation
# (e.g. SQLModel under sqlmodel/).
# See src/features/kanban/adapters/outbound/persistence/ for the canonical example.
from src.features._template.application.ports.outbound.example_repository import (
    ExampleRepositoryPort,
)
from src.features._template.domain.errors import TemplateDomainError
from src.features._template.domain.models.example_aggregate import ExampleAggregate
from src.platform.shared.result import Err, Ok, Result


class InMemoryExampleRepository(ExampleRepositoryPort):
    """TODO(template): swap for a real persistence adapter."""

    def __init__(self) -> None:
        self._store: dict[str, ExampleAggregate] = {}

    def find_by_id(
        self, entity_id: str
    ) -> Result[ExampleAggregate, TemplateDomainError]:
        entity = self._store.get(entity_id)
        if entity is None:
            return Err(TemplateDomainError.NOT_FOUND)
        return Ok(entity)

    def save(self, entity: ExampleAggregate) -> None:
        self._store[entity.id] = entity
