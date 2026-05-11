"""Authorization (ReBAC) primitives for the auth feature.

The application layer depends on ``AuthorizationPort`` from ``ports``;
adapters under ``src/features/auth/adapters/outbound/authorization/``
provide concrete implementations (in-repo SQLModel default, SpiceDB stub).

The Zanzibar-style relationship model is encoded across:

* ``ports.py``    — the application-side port contract.
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

from src.features.auth.application.authorization.actions import relations_for
from src.features.auth.application.authorization.errors import NotAuthorizedError
from src.features.auth.application.authorization.hierarchy import expand_relations
from src.features.auth.application.authorization.ports import AuthorizationPort
from src.features.auth.application.authorization.registry import (
    AuthorizationRegistry,
)
from src.features.auth.application.authorization.resource_graph import (
    ParentResolver,
)
from src.features.auth.application.authorization.types import Relationship

__all__ = [
    "AuthorizationPort",
    "AuthorizationRegistry",
    "NotAuthorizedError",
    "ParentResolver",
    "Relationship",
    "expand_relations",
    "relations_for",
]
