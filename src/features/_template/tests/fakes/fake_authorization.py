"""In-memory :class:`AuthorizationPort` for unit and e2e tests.

Honours the AuthorizationPort contract (the same contract the SQLModel
adapter satisfies) including hierarchy expansion through the registry's
``relations_for`` and ``has_stored_relations`` methods, so tests that
exercise authorization-aware flows do not require Postgres.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.features.authorization.application.errors import UnknownActionError
from src.features.authorization.application.ports.authorization_port import (
    LOOKUP_DEFAULT_LIMIT,
    LOOKUP_MAX_LIMIT,
)
from src.features.authorization.application.registry import AuthorizationRegistry
from src.features.authorization.application.types import Relationship


@dataclass(slots=True)
class FakeAuthorization:
    """Tuple-store with registry-aware hierarchy and parent-walk resolution."""

    registry: AuthorizationRegistry
    _tuples: set[tuple[str, str, str, str, str]] = field(default_factory=set)
    user_authz_version_bumps: list[UUID] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience used by tests
    # ------------------------------------------------------------------
    def seed(self, relationship: Relationship) -> None:
        self._tuples.add(self._key(relationship))

    @staticmethod
    def _key(r: Relationship) -> tuple[str, str, str, str, str]:
        return (
            r.resource_type,
            r.resource_id,
            r.relation,
            r.subject_type,
            r.subject_id,
        )

    # ------------------------------------------------------------------
    # AuthorizationPort
    # ------------------------------------------------------------------
    def check(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        resolved_type, resolved_id = self._resolve_storage_type(
            resource_type, resource_id
        )
        if resolved_type is None or resolved_id is None:
            return False
        try:
            relations = self.registry.relations_for(resolved_type, action)
        except (KeyError, UnknownActionError) as err:
            raise UnknownActionError(
                f"Unknown action {action!r} on resource_type {resource_type!r}"
            ) from err
        for relation in relations:
            if (
                resolved_type,
                resolved_id,
                relation,
                "user",
                str(user_id),
            ) in self._tuples:
                return True
        return False

    def lookup_resources(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        limit: int = LOOKUP_DEFAULT_LIMIT,
    ) -> list[str]:
        capped = min(limit, LOOKUP_MAX_LIMIT)
        try:
            relations = self.registry.relations_for(resource_type, action)
        except (KeyError, UnknownActionError):
            return []
        seen: list[str] = []
        for rt, rid, rel, st, sid in self._tuples:
            if (
                rt == resource_type
                and rel in relations
                and st == "user"
                and sid == str(user_id)
                and rid not in seen
            ):
                seen.append(rid)
                if len(seen) == capped:
                    break
        return seen

    def lookup_subjects(
        self,
        *,
        resource_type: str,
        resource_id: str,
        relation: str,
    ) -> list[UUID]:
        out: list[UUID] = []
        for rt, rid, rel, st, sid in self._tuples:
            if (
                rt == resource_type
                and rid == resource_id
                and rel == relation
                and st == "user"
            ):
                out.append(UUID(sid))
        return out

    def write_relationships(self, tuples: list[Relationship]) -> None:
        for relationship in tuples:
            self._tuples.add(self._key(relationship))
            if relationship.subject_type == "user":
                self.user_authz_version_bumps.append(UUID(relationship.subject_id))

    def delete_relationships(self, tuples: list[Relationship]) -> None:
        for relationship in tuples:
            self._tuples.discard(self._key(relationship))
            if relationship.subject_type == "user":
                self.user_authz_version_bumps.append(UUID(relationship.subject_id))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _resolve_storage_type(
        self, resource_type: str, resource_id: str
    ) -> tuple[str | None, str | None]:
        current_type: str | None = resource_type
        current_id: str | None = resource_id
        while current_type is not None and current_id is not None:
            if self.registry.has_stored_relations(current_type):
                return current_type, current_id
            parent = self.registry.parent_of(current_type, current_id)
            if parent is None:
                return None, None
            current_type, current_id = parent
        return None, None


__all__ = ["FakeAuthorization"]
