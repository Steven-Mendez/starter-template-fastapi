"""In-memory :class:`ThingRepositoryPort` for unit and e2e tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.features._template.domain.models.thing import Thing


@dataclass(slots=True)
class FakeThingRepository:
    _by_id: dict[UUID, Thing] = field(default_factory=dict)

    def add(self, thing: Thing) -> None:
        if thing.id in self._by_id:
            raise KeyError(f"Thing {thing.id} already exists")
        self._by_id[thing.id] = thing

    def get(self, thing_id: UUID) -> Thing | None:
        return self._by_id.get(thing_id)

    def list_by_ids(self, ids: list[UUID]) -> list[Thing]:
        return [self._by_id[i] for i in ids if i in self._by_id]

    def update(self, thing: Thing) -> None:
        if thing.id not in self._by_id:
            raise KeyError(f"Thing {thing.id} does not exist")
        self._by_id[thing.id] = thing

    def delete(self, thing_id: UUID) -> None:
        self._by_id.pop(thing_id, None)
