"""In-memory fake repository for unit testing the _template feature."""

from __future__ import annotations

from src.features._template.domain.errors import TemplateDomainError
from src.features._template.domain.models.example_aggregate import ExampleAggregate
from src.platform.shared.result import Err, Ok, Result


class FakeExampleRepository:
    """Simple dict-backed repository satisfying ``ExampleRepositoryPort``."""

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
