"""GetThing use case."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features._template.application.errors import ApplicationError
from src.features._template.application.ports.outbound.thing_repository import (
    ThingRepositoryPort,
)
from src.features._template.domain.models.thing import Thing
from src.platform.shared.result import Err, Ok, Result


@dataclass(frozen=True, slots=True)
class GetThingQuery:
    thing_id: UUID


@dataclass(slots=True)
class GetThingUseCase:
    repository: ThingRepositoryPort

    def execute(self, query: GetThingQuery) -> Result[Thing, ApplicationError]:
        thing = self.repository.get(query.thing_id)
        if thing is None:
            return Err(ApplicationError.NOT_FOUND)
        return Ok(thing)
