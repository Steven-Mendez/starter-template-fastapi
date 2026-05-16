"""Application-side authorization port (Zanzibar-flavored API).

The port is the single boundary between the application layer and any
authorization engine. The in-repo SQLModel adapter implements this
Protocol, and it remains the single swap boundary so a future ReBAC
backend can be introduced as one new adapter.

The five methods mirror the Zanzibar / OpenFGA public API so a reader
who learns this port can read a Zanzibar-style system's documentation
without retraining:

* ``check`` ↔ Zanzibar ``Check`` / OpenFGA ``Check``
* ``lookup_resources`` ↔ Zanzibar ``LookupResources``
* ``lookup_subjects`` ↔ Zanzibar ``LookupSubjects``
* ``write_relationships`` ↔ Zanzibar ``Write`` relationships
* ``delete_relationships`` ↔ Zanzibar ``Delete`` relationships
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from features.authorization.application.types import Relationship

# Default page size for ``lookup_resources`` / ``lookup_subjects``.
# ``LOOKUP_MAX_LIMIT`` is the hard cap the port enforces for both lookup
# methods — see Decision 4 in the design doc for the rationale (a single
# concurrency budget is easier to reason about than per-method caps).
LOOKUP_DEFAULT_LIMIT: int = 100
LOOKUP_MAX_LIMIT: int = 1000


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
        limit: int | None = None,
    ) -> list[UUID]:
        """Return user ids that hold ``relation`` on the resource.

        Hierarchy is applied so subjects with a superior relation are
        included. The optional ``limit`` parameter is clamped to
        ``LOOKUP_MAX_LIMIT``; passing ``None`` (the default) also applies
        the cap so callers never receive an unbounded result.
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
