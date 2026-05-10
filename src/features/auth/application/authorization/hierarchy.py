"""Relation hierarchy expansion.

Hierarchy is per-resource-type so we can evolve kanban relations
independently of system relations. Expansion is the closure of
"any superior relation also satisfies the inferior one" — e.g.,
``owner`` satisfies a check that requires ``writer`` or ``reader``.

In Zanzibar terms this is a "userset rewrite" expressed in code.
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

from src.features.auth.application.authorization.errors import UnknownActionError

# Each entry maps a target relation to the set of relations that satisfy it.
# ``reader`` is satisfied by anyone with reader, writer, or owner; ``owner``
# is satisfied only by an explicit owner tuple.
KANBAN_RELATION_HIERARCHY: dict[str, frozenset[str]] = {
    "reader": frozenset({"reader", "writer", "owner"}),
    "writer": frozenset({"writer", "owner"}),
    "owner": frozenset({"owner"}),
}

SYSTEM_RELATION_HIERARCHY: dict[str, frozenset[str]] = {
    "admin": frozenset({"admin"}),
}

_HIERARCHIES: dict[str, dict[str, frozenset[str]]] = {
    "kanban": KANBAN_RELATION_HIERARCHY,
    "column": KANBAN_RELATION_HIERARCHY,
    "card": KANBAN_RELATION_HIERARCHY,
    "system": SYSTEM_RELATION_HIERARCHY,
}


def expand_relations(resource_type: str, relations: frozenset[str]) -> frozenset[str]:
    """Return every relation that, if held, satisfies any of the given relations.

    For kanban, ``expand_relations("kanban", {"reader"})`` returns
    ``{reader, writer, owner}``.  ``expand_relations("kanban", {"owner"})``
    returns ``{owner}``.

    Raises:
        UnknownActionError: If ``resource_type`` has no defined hierarchy or
            if any input relation is not declared in the hierarchy.
    """
    hierarchy = _HIERARCHIES.get(resource_type)
    if hierarchy is None:
        raise UnknownActionError(
            f"No relation hierarchy defined for resource_type {resource_type!r}"
        )
    expanded: set[str] = set()
    for relation in relations:
        members = hierarchy.get(relation)
        if members is None:
            raise UnknownActionError(
                f"Unknown relation {relation!r} for resource_type {resource_type!r}"
            )
        expanded.update(members)
    return frozenset(expanded)
