"""In-memory :class:`AuthorizationPort` fake for unit and contract tests.

Mirrors the SQLModel-backed adapter's externally observable contract — the
relation hierarchy from the supplied :class:`AuthorizationRegistry` is
walked at check time and inherited resource types delegate to their
nearest leaf ancestor exactly like the real engine does. The fake stores
tuples in a plain ``set`` so a single subclass can run the
:class:`AuthorizationContract` scenarios against it without spinning up
SQLite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from features.authorization.application.ports.authorization_port import (
    LOOKUP_DEFAULT_LIMIT,
    LOOKUP_MAX_LIMIT,
)
from features.authorization.application.ports.outbound import (
    UserAuthzVersionPort,
)
from features.authorization.application.registry import AuthorizationRegistry
from features.authorization.application.types import Relationship


@dataclass(slots=True)
class FakeAuthorizationAdapter:
    """In-memory adapter implementing the full :class:`AuthorizationPort`.

    The adapter stores tuples in a set keyed by every field of
    :class:`Relationship` so duplicate writes are idempotent (the same
    semantics the real adapter achieves via its existence check before
    insert). Hierarchy resolution and parent walks are delegated to the
    supplied :class:`AuthorizationRegistry` — the same registry the real
    adapter consults — so contract scenarios run against identical
    expansion rules on both bindings.
    """

    registry: AuthorizationRegistry
    user_authz_version: UserAuthzVersionPort
    _tuples: set[Relationship] = field(default_factory=set)

    # ── Read API ──────────────────────────────────────────────────────────────

    def check(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        required = self.registry.relations_for(resource_type, action)
        walked_type, walked_id = resource_type, resource_id
        while not self.registry.has_stored_relations(walked_type):
            parent = self.registry.parent_of(walked_type, walked_id)
            if parent is None:
                return False
            walked_type, walked_id = parent
        expanded = self.registry.expand_relations(walked_type, required)
        subject_id = str(user_id)
        return any(
            tup.resource_type == walked_type
            and tup.resource_id == walked_id
            and tup.relation in expanded
            and tup.subject_type == "user"
            and tup.subject_id == subject_id
            for tup in self._tuples
        )

    def lookup_resources(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        limit: int = LOOKUP_DEFAULT_LIMIT,
    ) -> list[str]:
        capped = max(1, min(limit, LOOKUP_MAX_LIMIT))
        required = self.registry.relations_for(resource_type, action)
        stored_type = self.registry.nearest_leaf_type(resource_type)
        expanded = self.registry.expand_relations(stored_type, required)
        subject_id = str(user_id)
        seen: set[str] = set()
        out: list[str] = []
        # Sort for deterministic ordering, matching the real adapter's
        # ``ORDER BY resource_id`` clause.
        for tup in sorted(
            self._tuples,
            key=lambda t: (t.resource_id, t.relation),
        ):
            if (
                tup.resource_type != stored_type
                or tup.subject_type != "user"
                or tup.subject_id != subject_id
                or tup.relation not in expanded
            ):
                continue
            if tup.resource_id in seen:
                continue
            seen.add(tup.resource_id)
            out.append(tup.resource_id)
            if len(out) >= capped:
                break
        return out

    def lookup_subjects(
        self,
        *,
        resource_type: str,
        resource_id: str,
        relation: str,
        limit: int | None = None,
    ) -> list[UUID]:
        capped = (
            LOOKUP_MAX_LIMIT if limit is None else max(1, min(limit, LOOKUP_MAX_LIMIT))
        )
        expanded = self.registry.expand_relations(resource_type, frozenset({relation}))
        seen: set[UUID] = set()
        out: list[UUID] = []
        for tup in self._tuples:
            if (
                tup.resource_type != resource_type
                or tup.resource_id != resource_id
                or tup.subject_type != "user"
                or tup.relation not in expanded
            ):
                continue
            try:
                user_id = UUID(tup.subject_id)
            except (TypeError, ValueError):
                continue
            if user_id in seen:
                continue
            seen.add(user_id)
            out.append(user_id)
            if len(out) >= capped:
                break
        return out

    # ── Write API ─────────────────────────────────────────────────────────────

    def write_relationships(self, tuples: list[Relationship]) -> None:
        if not tuples:
            return
        for tup in tuples:
            self._tuples.add(tup)
        self._bump_affected_users(tuples)

    def delete_relationships(self, tuples: list[Relationship]) -> None:
        if not tuples:
            return
        for tup in tuples:
            self._tuples.discard(tup)
        self._bump_affected_users(tuples)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _bump_affected_users(self, tuples: list[Relationship]) -> None:
        bumped: set[UUID] = set()
        for tup in tuples:
            if tup.subject_type != "user":
                continue
            try:
                user_id = UUID(tup.subject_id)
            except (TypeError, ValueError):
                continue
            if user_id in bumped:
                continue
            bumped.add(user_id)
            self.user_authz_version.bump(user_id)
