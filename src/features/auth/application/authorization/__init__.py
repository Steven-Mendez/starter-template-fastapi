"""Authorization (ReBAC) primitives for the auth feature.

The application layer depends on ``AuthorizationPort`` from ``ports``;
adapters under ``src/features/auth/adapters/outbound/authorization/``
provide concrete implementations (in-repo SQLModel default, SpiceDB stub).

The Zanzibar-style relationship model is encoded across:

* ``ports.py``    — the application-side port contract.
* ``actions.py``  — ``(resource_type, action) -> required relations`` map.
* ``hierarchy.py``— relation expansion (e.g., ``owner`` covers ``writer``).
* ``resource_graph.py`` — parent walk for cross-resource inheritance.
* ``types.py``    — the ``Relationship`` value object passed across the port.
* ``errors.py``   — ``NotAuthorizedError`` for application-level failures.
"""

from __future__ import annotations

from src.features.auth.application.authorization.actions import (
    ACTIONS,
    relations_for,
)
from src.features.auth.application.authorization.errors import NotAuthorizedError
from src.features.auth.application.authorization.hierarchy import (
    KANBAN_RELATION_HIERARCHY,
    SYSTEM_RELATION_HIERARCHY,
    expand_relations,
)
from src.features.auth.application.authorization.ports import AuthorizationPort
from src.features.auth.application.authorization.resource_graph import (
    ParentResolver,
)
from src.features.auth.application.authorization.types import Relationship

__all__ = [
    "ACTIONS",
    "AuthorizationPort",
    "KANBAN_RELATION_HIERARCHY",
    "NotAuthorizedError",
    "ParentResolver",
    "Relationship",
    "SYSTEM_RELATION_HIERARCHY",
    "expand_relations",
    "relations_for",
]
