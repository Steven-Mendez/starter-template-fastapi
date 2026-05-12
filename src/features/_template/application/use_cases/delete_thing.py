"""DeleteThing use case."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features._template.application.errors import ApplicationError
from src.features._template.application.ports.outbound.unit_of_work import (
    UnitOfWorkPort,
)
from src.features.authorization.application.types import Relationship
from src.platform.shared.result import Err, Ok, Result

_THING_RELATIONS = ("owner", "writer", "reader")


@dataclass(frozen=True, slots=True)
class DeleteThingCommand:
    thing_id: UUID


@dataclass(slots=True)
class DeleteThingUseCase:
    """Delete a thing and all its authorization tuples atomically."""

    uow: UnitOfWorkPort

    def execute(self, command: DeleteThingCommand) -> Result[None, ApplicationError]:
        with self.uow.begin() as handle:
            existing = handle.things.get(command.thing_id)
            if existing is None:
                return Err(ApplicationError.NOT_FOUND)
            handle.things.delete(command.thing_id)
            tuples: list[Relationship] = []
            for relation in _THING_RELATIONS:
                for subject_id in handle.authorization.lookup_subjects(
                    resource_type="thing",
                    resource_id=str(command.thing_id),
                    relation=relation,
                ):
                    tuples.append(
                        Relationship(
                            resource_type="thing",
                            resource_id=str(command.thing_id),
                            relation=relation,
                            subject_type="user",
                            subject_id=str(subject_id),
                        )
                    )
            if tuples:
                handle.authorization.delete_relationships(tuples)
        return Ok(None)
