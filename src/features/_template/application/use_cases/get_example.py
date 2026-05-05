from __future__ import annotations

from dataclasses import dataclass

from src.features._template.application.errors import ApplicationError
from src.features._template.application.ports.outbound.example_repository import (
    ExampleRepositoryPort,
)
from src.features._template.domain.models.example_aggregate import ExampleAggregate
from src.platform.shared.result import Err, Ok, Result


@dataclass(frozen=True, slots=True)
class GetExampleQuery:
    """TODO(template): replace with your query DTO."""

    entity_id: str


@dataclass(slots=True)
class GetExampleUseCase:
    """TODO(template): orchestrate domain + outbound ports.

    Use cases:
    - depend on outbound ports via constructor injection,
    - never import adapters,
    - return ``Result[T, ApplicationError]``.
    """

    repository: ExampleRepositoryPort

    def execute(
        self, query: GetExampleQuery
    ) -> Result[ExampleAggregate, ApplicationError]:
        result = self.repository.find_by_id(query.entity_id)
        if isinstance(result, Err):
            return Err(ApplicationError.NOT_FOUND)
        return Ok(result.value)
