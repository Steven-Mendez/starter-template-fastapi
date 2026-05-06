"""Scaffold in-memory adapter that keeps copied features runnable end-to-end.

Replace this with the real outbound adapter (e.g. SQLModel) once the
copied feature has settled on a persistence story.
"""

from __future__ import annotations

from src.features._template.application.ports.outbound.example_repository import (
    ExampleRepositoryPort,
)
from src.features._template.domain.errors import TemplateDomainError
from src.features._template.domain.models.example_aggregate import ExampleAggregate
from src.platform.shared.result import Err, Ok, Result


class InMemoryExampleRepository(ExampleRepositoryPort):
    """Minimal in-memory repository for the copied feature scaffold."""

    def __init__(self) -> None:
        """Initialise an empty in-memory store keyed by aggregate id."""
        self._store: dict[str, ExampleAggregate] = {}

    def find_by_id(
        self, entity_id: str
    ) -> Result[ExampleAggregate, TemplateDomainError]:
        """Return the aggregate stored under ``entity_id`` or ``NOT_FOUND``."""
        entity = self._store.get(entity_id)
        if entity is None:
            return Err(TemplateDomainError.NOT_FOUND)
        return Ok(entity)

    def save(self, entity: ExampleAggregate) -> None:
        """Store the aggregate, replacing any previous entry with the same id."""
        self._store[entity.id] = entity
