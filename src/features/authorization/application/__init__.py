"""Authorization (ReBAC) application layer.

Adapters under ``src/features/authorization/adapters/outbound/`` provide
concrete implementations of :class:`AuthorizationPort` (in-repo
SQLModel default; SpiceDB stub).

The Zanzibar-style relationship model is encoded across:

* ``ports/authorization_port.py`` — the application-side port contract.
* ``registry.py`` — the runtime ``AuthorizationRegistry`` features
  populate at startup with their resource types, actions, hierarchies,
  and parent-walk callables. The engine reads everything it needs from
  the registry; no feature-specific vocabulary lives in this module.
* ``actions.py``  — thin ``relations_for(registry, ...)`` wrapper.
* ``hierarchy.py``— thin ``expand_relations(registry, ...)`` wrapper.
* ``resource_graph.py`` — the ``ParentResolver`` Protocol for the walk.
* ``types.py``    — the ``Relationship`` value object passed across the port.
* ``errors.py``   — ``NotAuthorizedError`` for application-level failures.
"""

from __future__ import annotations

from src.features.authorization.application.actions import relations_for
from src.features.authorization.application.errors import NotAuthorizedError
from src.features.authorization.application.hierarchy import expand_relations
from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from src.features.authorization.application.registry import AuthorizationRegistry
from src.features.authorization.application.resource_graph import ParentResolver
from src.features.authorization.application.types import Relationship
from src.features.authorization.application.use_cases import BootstrapSystemAdmin

__all__ = [
    "AuthorizationPort",
    "AuthorizationRegistry",
    "BootstrapSystemAdmin",
    "NotAuthorizedError",
    "ParentResolver",
    "Relationship",
    "expand_relations",
    "relations_for",
]
