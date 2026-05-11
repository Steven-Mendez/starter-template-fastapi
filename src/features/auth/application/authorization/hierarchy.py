"""Relation hierarchy expansion (registry-backed).

The hierarchy itself lives in :class:`AuthorizationRegistry`; this module
exists as a thin functional wrapper for callers that prefer a free
function. The Zanzibar-style "userset rewrite" — superior relations
satisfying inferior checks — is encoded as the per-resource-type
``hierarchy`` map a feature passes to ``register_resource_type``.

For SpiceDB this would be a schema fragment such as::

    definition kanban {
        relation reader: user
        relation writer: user
        relation owner: user

        permission read   = reader + writer + owner
        permission update = writer + owner
        permission delete = owner
    }
"""

from __future__ import annotations

from src.features.auth.application.authorization.registry import (
    AuthorizationRegistry,
)


def expand_relations(
    registry: AuthorizationRegistry,
    resource_type: str,
    relations: frozenset[str],
) -> frozenset[str]:
    """Return every relation that, if held, satisfies any input relation."""
    return registry.expand_relations(resource_type, relations)
