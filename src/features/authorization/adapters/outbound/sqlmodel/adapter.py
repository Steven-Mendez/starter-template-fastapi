"""SQLModel-backed implementation of ``AuthorizationPort``.

The default adapter resolves the relation hierarchy and cross-resource
inheritance at *check time* by consulting the
:class:`AuthorizationRegistry`. Inherited resource types (e.g., a child
resource that does not store its own tuples) declare a ``parent_of``
callable at registration; the engine walks parents until it lands on a
leaf type with stored tuples, then evaluates the original action against
the parent's hierarchy.

Scaling note
============
Check-time resolution keeps writes cheap and the model easy to read,
but the query cost is roughly ``O(walked_resources * hierarchy_size)``.
For high-throughput deployments where ``lookup_resources`` returns
thousands of ids per request, switch to a real ReBAC engine
(SpiceDB / OpenFGA / AuthZed Cloud) — they materialize implied tuples
at write time using a watch-and-expand pipeline. The port boundary is
designed so that swap is one adapter, not an engine rewrite.

The adapter ships in two flavours so a feature's use cases can write
relationship tuples inside the same DB transaction as the resource write:

* :class:`SQLModelAuthorizationAdapter` owns its own engine and opens
  a fresh session per call. Suitable for read paths and standalone writes.
* :class:`SessionSQLModelAuthorizationAdapter` borrows an existing
  session managed by an outer unit-of-work, so a feature's "create
  resource + initial-owner-tuple" pair commits or rolls back together.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app_platform.persistence.sqlmodel.authorization.models import RelationshipTable
from features.authorization.application.ports.authorization_port import (
    LOOKUP_DEFAULT_LIMIT,
    LOOKUP_MAX_LIMIT,
)
from features.authorization.application.ports.outbound import (
    UserAuthzVersionPort,
)
from features.authorization.application.registry import AuthorizationRegistry
from features.authorization.application.types import Relationship


def _user_subject_ids(tuples: list[Relationship]) -> set[UUID]:
    """Return distinct UUIDs for every ``user`` subject in the input."""
    out: set[UUID] = set()
    for relationship in tuples:
        if relationship.subject_type != "user":
            continue
        try:
            out.add(UUID(relationship.subject_id))
        except (ValueError, TypeError):
            # Non-UUID subject_id (future-proofing for non-user subjects);
            # the engine treats it as not-a-user and skips authz_version bump.
            continue
    return out


class _BaseAuthorizationAdapter:
    """Shared engine logic; subclasses provide the session strategy."""

    def __init__(
        self,
        registry: AuthorizationRegistry,
        user_authz_version: UserAuthzVersionPort,
    ) -> None:
        self._registry = registry
        self._user_authz_version = user_authz_version

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        raise NotImplementedError

    @contextmanager
    def _write_session_scope(self) -> Iterator[Session]:
        raise NotImplementedError

    # ── Read API ──────────────────────────────────────────────────────────────

    def check(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        """Walk parents to a stored type, then resolve hierarchy + match."""
        # Surface unknown types before walking so the HTTP layer can return
        # 500 (programmer error) instead of a silent denied check.
        required = self._registry.relations_for(resource_type, action)

        walked_type, walked_id = resource_type, resource_id
        while not self._registry.has_stored_relations(walked_type):
            parent = self._registry.parent_of(walked_type, walked_id)
            if parent is None:
                return False
            walked_type, walked_id = parent

        expanded = self._registry.expand_relations(walked_type, required)
        with self._session_scope() as session:
            return self._exists_relation(
                session,
                resource_type=walked_type,
                resource_id=walked_id,
                relations=expanded,
                user_id=user_id,
            )

    def lookup_resources(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        limit: int = LOOKUP_DEFAULT_LIMIT,
    ) -> list[str]:
        """Return resource ids the user can ``action`` on, capped at the limit.

        Inherited types redirect to their nearest leaf ancestor because only
        the leaf has stored tuples; the access granted by a single leaf
        tuple covers every inherited child anyway.
        """
        capped_limit = max(1, min(limit, LOOKUP_MAX_LIMIT))
        required = self._registry.relations_for(resource_type, action)
        stored_type = self._registry.nearest_leaf_type(resource_type)
        expanded = self._registry.expand_relations(stored_type, required)

        with self._session_scope() as session:
            rows = session.exec(
                select(RelationshipTable.resource_id)
                .where(RelationshipTable.resource_type == stored_type)
                .where(cast(Any, RelationshipTable.relation).in_(expanded))
                .where(RelationshipTable.subject_type == "user")
                .where(RelationshipTable.subject_id == str(user_id))
                .order_by("resource_id")
                .limit(capped_limit)
            ).all()
        # Deduplicate (a user might hold multiple matching relations on the
        # same resource, e.g. owner+writer) while preserving order.
        seen: set[str] = set()
        out: list[str] = []
        for resource_id in rows:
            if resource_id in seen:
                continue
            seen.add(resource_id)
            out.append(resource_id)
        return out

    def lookup_subjects(
        self,
        *,
        resource_type: str,
        resource_id: str,
        relation: str,
    ) -> list[UUID]:
        """Return user ids holding ``relation`` (or any superior) on the resource."""
        expanded = self._registry.expand_relations(resource_type, frozenset({relation}))
        with self._session_scope() as session:
            rows = session.exec(
                select(RelationshipTable.subject_id)
                .where(RelationshipTable.resource_type == resource_type)
                .where(RelationshipTable.resource_id == resource_id)
                .where(cast(Any, RelationshipTable.relation).in_(expanded))
                .where(RelationshipTable.subject_type == "user")
            ).all()
        out: list[UUID] = []
        seen: set[UUID] = set()
        for subject_id in rows:
            try:
                user_id = UUID(subject_id)
            except (ValueError, TypeError):
                continue
            if user_id in seen:
                continue
            seen.add(user_id)
            out.append(user_id)
        return out

    # ── Write API ─────────────────────────────────────────────────────────────

    def write_relationships(self, tuples: list[Relationship]) -> None:
        """Persist tuples (idempotent) and bump authz_version for affected users.

        The relationship inserts and the version bump for every affected
        user share one ``_write_session_scope`` so they commit (or roll
        back) atomically. If any bump raises, the surrounding session
        rolls back and no relationship row lands either.

        Idempotency is achieved by an existence check before insert rather
        than relying on the unique constraint, so a duplicate tuple in a
        batch does not poison the surrounding transaction. The constraint
        is still the ultimate guard against races between concurrent writers.
        """
        if not tuples:
            return
        with self._write_session_scope() as session:
            for relationship in tuples:
                exists = session.exec(
                    select(RelationshipTable.id)
                    .where(
                        RelationshipTable.resource_type == relationship.resource_type
                    )
                    .where(RelationshipTable.resource_id == relationship.resource_id)
                    .where(RelationshipTable.relation == relationship.relation)
                    .where(RelationshipTable.subject_type == relationship.subject_type)
                    .where(RelationshipTable.subject_id == relationship.subject_id)
                    .limit(1)
                ).one_or_none()
                if exists is not None:
                    continue
                session.add(
                    RelationshipTable(
                        resource_type=relationship.resource_type,
                        resource_id=relationship.resource_id,
                        relation=relationship.relation,
                        subject_type=relationship.subject_type,
                        subject_id=relationship.subject_id,
                    )
                )
            session.flush()
            self._bump_affected_users(session, tuples)

    def delete_relationships(self, tuples: list[Relationship]) -> None:
        """Remove tuples and bump authz_version for affected users.

        The deletes and the version bump for every affected user share
        one ``_write_session_scope`` so they commit (or roll back)
        atomically.
        """
        if not tuples:
            return
        with self._write_session_scope() as session:
            for relationship in tuples:
                session.execute(
                    delete(RelationshipTable).where(
                        cast(
                            Any,
                            RelationshipTable.resource_type
                            == relationship.resource_type,
                        ),
                        cast(
                            Any,
                            RelationshipTable.resource_id == relationship.resource_id,
                        ),
                        cast(Any, RelationshipTable.relation == relationship.relation),
                        cast(
                            Any,
                            RelationshipTable.subject_type == relationship.subject_type,
                        ),
                        cast(
                            Any,
                            RelationshipTable.subject_id == relationship.subject_id,
                        ),
                    )
                )
            self._bump_affected_users(session, tuples)

    def _bump_affected_users(
        self, session: Session, tuples: list[Relationship]
    ) -> None:
        """Bump ``authz_version`` once per affected ``user:*`` subject.

        Multiple tuples in the same call may touch the same subject;
        ``_user_subject_ids`` dedupes them so the bump is exactly-once
        per user per transaction. The bump runs inside the caller's
        session so it shares the surrounding commit/rollback.
        """
        for user_id in _user_subject_ids(tuples):
            self._user_authz_version.bump_in_session(session, user_id)

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _exists_relation(
        session: Session,
        *,
        resource_type: str,
        resource_id: str,
        relations: frozenset[str],
        user_id: UUID,
    ) -> bool:
        row = session.exec(
            select(RelationshipTable.id)
            .where(RelationshipTable.resource_type == resource_type)
            .where(RelationshipTable.resource_id == resource_id)
            .where(cast(Any, RelationshipTable.relation).in_(relations))
            .where(RelationshipTable.subject_type == "user")
            .where(RelationshipTable.subject_id == str(user_id))
            .limit(1)
        ).one_or_none()
        return row is not None


class SQLModelAuthorizationAdapter(_BaseAuthorizationAdapter):
    """Engine-owning adapter for the authorization feature container.

    Each call opens a fresh session against the shared engine. Used for
    read paths (``check``, ``lookup_resources``, ``lookup_subjects``) and
    standalone writes (e.g., bootstrap, admin grants).
    """

    def __init__(
        self,
        engine: Engine,
        registry: AuthorizationRegistry,
        user_authz_version: UserAuthzVersionPort,
    ) -> None:
        super().__init__(registry=registry, user_authz_version=user_authz_version)
        self._engine = engine

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        with Session(self._engine, expire_on_commit=False) as session:
            yield session

    @contextmanager
    def _write_session_scope(self) -> Iterator[Session]:
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise


class SessionSQLModelAuthorizationAdapter(_BaseAuthorizationAdapter):
    """Adapter that borrows a Session managed by an outer unit-of-work.

    Used by a feature's "create resource" use case: the initial-owner-
    tuple write must commit atomically with the resource insert, so both
    operations need to share the same Session.
    """

    def __init__(
        self,
        session: Session,
        registry: AuthorizationRegistry,
        user_authz_version: UserAuthzVersionPort,
    ) -> None:
        super().__init__(registry=registry, user_authz_version=user_authz_version)
        self._session = session

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        yield self._session

    @contextmanager
    def _write_session_scope(self) -> Iterator[Session]:
        # The outer UoW commits or rolls back; here we only flush so any
        # IntegrityError (duplicate tuple) surfaces synchronously.
        yield self._session
