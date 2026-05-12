"""Outbound port: transactional boundary spanning repo writes and authz writes.

Use cases that mutate state acquire a :class:`UnitOfWorkPort`. Within the
``with`` block they receive a fresh :class:`ThingRepositoryPort` and a
session-scoped :class:`AuthorizationPort`. Both writes commit (or roll
back) atomically.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from src.features._template.application.ports.outbound.thing_repository import (
    ThingRepositoryPort,
)
from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)


@dataclass(frozen=True, slots=True)
class TemplateUoWHandle:
    """View of the transactional resources exposed inside a unit of work."""

    things: ThingRepositoryPort
    authorization: AuthorizationPort


class UnitOfWorkPort(Protocol):
    """Open a transactional scope that yields a :class:`TemplateUoWHandle`."""

    def begin(self) -> AbstractContextManager[TemplateUoWHandle]:
        """Return a context manager that commits on exit and rolls back on error."""
        ...
