"""Action -> required-relations dispatch (registry-backed).

The dispatch table lives in :class:`AuthorizationRegistry`; this module
exists as a thin functional wrapper for callers that prefer a free
function over a registry method. Both forms read the same map.

Each feature populates the registry from its composition root, so this
module is intentionally empty of feature-specific knowledge.
"""

from __future__ import annotations

from features.authorization.application.registry import AuthorizationRegistry


def relations_for(
    registry: AuthorizationRegistry, resource_type: str, action: str
) -> frozenset[str]:
    """Return the relation set that satisfies ``action`` on ``resource_type``."""
    return registry.relations_for(resource_type, action)
