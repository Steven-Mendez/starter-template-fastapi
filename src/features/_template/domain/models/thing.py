"""The :class:`Thing` aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.features._template.domain.errors import ThingNameRequiredError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Thing:
    """A simple named resource owned by exactly one user.

    Demonstrates the canonical aggregate pattern: an id-bearing entity with
    a small invariant (non-empty name) enforced in the constructor and any
    method that mutates the field.
    """

    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        self._validate_name(self.name)

    @classmethod
    def create(cls, *, name: str, owner_id: UUID) -> "Thing":
        """Construct a new :class:`Thing` with a fresh id."""
        cls._validate_name(name)
        return cls(id=uuid4(), name=name, owner_id=owner_id)

    def rename(self, new_name: str) -> "Thing":
        """Return a new :class:`Thing` with an updated name and bumped `updated_at`."""
        self._validate_name(new_name)
        return replace(self, name=new_name, updated_at=_utc_now())

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name or not name.strip():
            raise ThingNameRequiredError("Thing.name must be a non-empty string")
