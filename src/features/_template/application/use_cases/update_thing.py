"""UpdateThing use case (rename only)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features._template.application.errors import ApplicationError
from src.features._template.application.ports.outbound.unit_of_work import (
    UnitOfWorkPort,
)
from src.features._template.domain.errors import ThingNameRequiredError
from src.features._template.domain.models.thing import Thing
from src.platform.shared.result import Err, Ok, Result


@dataclass(frozen=True, slots=True)
class UpdateThingCommand:
    thing_id: UUID
    new_name: str


@dataclass(slots=True)
class UpdateThingUseCase:
    uow: UnitOfWorkPort

    def execute(self, command: UpdateThingCommand) -> Result[Thing, ApplicationError]:
        with self.uow.begin() as handle:
            existing = handle.things.get(command.thing_id)
            if existing is None:
                return Err(ApplicationError.NOT_FOUND)
            try:
                renamed = existing.rename(command.new_name)
            except ThingNameRequiredError:
                return Err(ApplicationError.NAME_REQUIRED)
            handle.things.update(renamed)
        return Ok(renamed)
