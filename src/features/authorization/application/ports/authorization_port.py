"""Application-side authorization port (Zanzibar-flavored API).

The port is the single boundary between the application layer and any
authorization engine. The two adapters that ship with the template
(in-repo SQLModel default; SpiceDB stub) implement this Protocol.

The five methods mirror the SpiceDB / OpenFGA public API so a reader
who learns this port can read either system's documentation without
retraining:

* ``check`` ↔ SpiceDB ``CheckPermission``
* ``lookup_resources`` ↔ SpiceDB ``LookupResources``
* ``lookup_subjects`` ↔ SpiceDB ``LookupSubjects``
* ``write_relationships`` ↔ SpiceDB ``WriteRelationships``
* ``delete_relationships`` ↔ SpiceDB ``DeleteRelationships``
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.features.authorization.application.types import Relationship

# Default page size for ``lookup_resources``. Mirrors the existing admin
# endpoint defaults (limit=100, max=500) so the API surface is uniform.
LOOKUP_DEFAULT_LIMIT: int = 100
LOOKUP_MAX_LIMIT: int = 500


class AuthorizationPort(Protocol):
    """Bidirectional authorization API.

    Implementations are responsible for resolving the relation hierarchy
    (e.g., ``owner ⊇ writer ⊇ reader``) and any cross-resource
    inheritance (an inherited child resource walks to its parent through
    a registry-supplied callable) without exposing those mechanics to
    callers.
    """

    def check(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        """Return ``True`` iff ``user_id`` is allowed to ``action`` on the resource.

        Args:
            user_id: Subject performing the action.
            action: An action declared in ``application/authorization/actions.py``
                for the given ``resource_type``.
            resource_type: A resource type registered on the
                ``AuthorizationRegistry`` (e.g., ``"system"``, plus
                whatever a feature has contributed at composition time).
            resource_id: The instance id; opaque to the port. For
                ``"system"`` resources the convention is ``"main"``.
        """
        ...

    def lookup_resources(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        limit: int = LOOKUP_DEFAULT_LIMIT,
    ) -> list[str]:
        """Return resource ids the user can ``action`` on, paginated.

        Args:
            user_id: Subject whose access is being enumerated.
            action: An action declared for the resource type.
            resource_type: The type of resource to enumerate.
            limit: Maximum result count (capped at ``LOOKUP_MAX_LIMIT``).
        """
        ...

    def lookup_subjects(
        self,
        *,
        resource_type: str,
        resource_id: str,
        relation: str,
    ) -> list[UUID]:
        """Return user ids that hold ``relation`` on the resource.

        Hierarchy is applied so subjects with a superior relation are
        included.
        """
        ...

    def write_relationships(self, tuples: list[Relationship]) -> None:
        """Persist relationship tuples (idempotent via the DB unique constraint).

        Implementations SHALL bump ``User.authz_version`` for every distinct
        user subject in ``tuples`` so any cached principal becomes stale.
        """
        ...

    def delete_relationships(self, tuples: list[Relationship]) -> None:
        """Remove relationship tuples; missing tuples are silently ignored.

        Implementations SHALL bump ``User.authz_version`` for every distinct
        user subject in ``tuples``.
        """
        ...
