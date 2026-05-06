from __future__ import annotations

# This scaffold adapter keeps copied features runnable while their real outbound
# adapter is still being designed.
from src.features._template.application.ports.outbound.example_repository import (
    ExampleRepositoryPort,
)
from src.features._template.domain.errors import TemplateDomainError
from src.features._template.domain.models.example_aggregate import ExampleAggregate
from src.platform.shared.result import Err, Ok, Result


class InMemoryExampleRepository(ExampleRepositoryPort):
    """Minimal in-memory repository for the copied feature scaffold."""

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
