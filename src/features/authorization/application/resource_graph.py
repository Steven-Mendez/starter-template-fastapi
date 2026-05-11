"""Cross-resource parent walk for computed inheritance.

Inherited resource types (e.g., a kanban ``card`` that does not store its
own relationship tuples) declare a ``parent_of`` callable at registration
time. The engine walks the chain at check time until it reaches a
resource type whose tuples are persisted, then evaluates the original
action against the parent's hierarchy.

Auth's authorization engine never imports another feature directly; the
``parent_of`` callable is supplied by whichever feature owns the
inherited resource.
"""

from __future__ import annotations

from typing import Protocol


class ParentResolver(Protocol):
    """Resolve the parent resource for an inherited child resource id.

    Implementations live in the feature that owns the resource type
    (e.g., kanban's lookup repository wraps board-id lookups for cards
    and columns). The registry holds one such callable per inherited
    type and consults it during the parent walk.
    """

    def parent_of(self, resource_type: str, resource_id: str) -> tuple[str, str] | None:
        """Return ``(parent_type, parent_id)`` for the child, or ``None`` if absent.

        SHALL NOT raise: a missing resource should produce a denied check,
        not an exception. Soft-deleted rows are treated as absent.
        """
        ...
