"""Outbound port: persistence contract for the :class:`Thing` aggregate."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.features._template.domain.models.thing import Thing


class ThingRepositoryPort(Protocol):
    """Read/write persistence for :class:`Thing` instances.

    Implementations live under ``adapters/outbound/persistence/`` and are
    constructed by the composition root. The application layer depends
    only on this Protocol, never on a concrete adapter.
    """

    def add(self, thing: Thing) -> None:
        """Persist a new thing. Raises if the id already exists."""
        ...

    def get(self, thing_id: UUID) -> Thing | None:
        """Return the thing with the given id, or ``None`` if absent."""
        ...

    def list_by_ids(self, ids: list[UUID]) -> list[Thing]:
        """Return all things whose id is in ``ids``, in any order.

        Missing ids are silently skipped.
        """
        ...

    def update(self, thing: Thing) -> None:
        """Persist mutations to an existing thing. Raises if the id is unknown."""
        ...

    def delete(self, thing_id: UUID) -> None:
        """Remove the thing with the given id. No-op if absent."""
        ...
