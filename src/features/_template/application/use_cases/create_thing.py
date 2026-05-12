"""CreateThing use case: writes the thing and the initial owner tuple atomically."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features._template.application.errors import ApplicationError
from src.features._template.application.ports.outbound.unit_of_work import (
    UnitOfWorkPort,
)
from src.features._template.domain.errors import ThingNameRequiredError
from src.features._template.domain.models.thing import Thing
from src.features.authorization.application.types import Relationship
from src.platform.shared.result import Err, Ok, Result


@dataclass(frozen=True, slots=True)
class CreateThingCommand:
    """Input DTO."""

    name: str
    owner_id: UUID


@dataclass(slots=True)
class CreateThingUseCase:
    """Create a thing and grant the actor the ``owner`` relation on it.

    The relationship tuple write participates in the same unit of work as
    the thing insert, so the resource and the authorization grant succeed
    or fail together.
    """

    uow: UnitOfWorkPort

    def execute(self, command: CreateThingCommand) -> Result[Thing, ApplicationError]:
        try:
            thing = Thing.create(name=command.name, owner_id=command.owner_id)
        except ThingNameRequiredError:
            return Err(ApplicationError.NAME_REQUIRED)

        with self.uow.begin() as handle:
            handle.things.add(thing)
            handle.authorization.write_relationships(
                [
                    Relationship(
                        resource_type="thing",
                        resource_id=str(thing.id),
                        relation="owner",
                        subject_type="user",
                        subject_id=str(command.owner_id),
                    )
                ]
            )

        return Ok(thing)
