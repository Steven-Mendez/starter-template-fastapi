"""SQLModel-backed :class:`AuthArtifactsCleanupPort` implementation.

Stages the GDPR-Art.17 scrub/delete writes on the active outbox-writer
session so the users-feature ``EraseUser`` transaction covers them
atomically with the user-row scrub.

The adapter falls back to an engine-owning transaction when the writer
is not session-backed (inline-dispatch e2e fakes), matching the
pattern :class:`SQLModelUserRepository.set_active_atomically_with` uses.
Integration tests exercise the writer-bound path against a real
PostgreSQL.

The audit-event scrub operates on PostgreSQL JSONB via the ``-`` operator;
on SQLite (used by the in-memory e2e fixture) the dialect coerces the
column to TEXT, so the adapter encodes the JSON membership update in
Python for that branch. Production runs on Postgres so the JSONB path
is what matters; the SQLite fallback exists only so the e2e suite still
ends up with PII-free rows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    CredentialTable,
    RefreshTokenTable,
    utc_now,
)

# Keys that this adapter strips from ``auth_audit_events.event_metadata``.
# Kept as a module-level constant so the PII inventory in
# ``docs/operations.md`` and this list can be cross-referenced.
_PII_METADATA_KEYS: tuple[str, ...] = ("family_id", "ip_address", "user_agent")


@dataclass(slots=True)
class SQLModelAuthArtifactsCleanupAdapter:
    """Scrub authentication-owned PII rows for a user inside a shared transaction."""

    engine: Engine

    def scrub_audit_events(self, writer: object, user_id: UUID) -> None:
        session = _writer_session(writer)
        if session is None:
            with Session(self.engine, expire_on_commit=False) as own:
                _scrub_audit_events_on_session(own, user_id)
                own.commit()
            return
        _scrub_audit_events_on_session(session, user_id)

    def delete_credentials_and_tokens(self, writer: object, user_id: UUID) -> None:
        session = _writer_session(writer)
        if session is None:
            with Session(self.engine, expire_on_commit=False) as own:
                _delete_artifacts_on_session(own, user_id)
                own.commit()
            return
        _delete_artifacts_on_session(session, user_id)

    def record_user_erased_event(
        self,
        writer: object,
        user_id: UUID,
        reason: str,
    ) -> None:
        # Payload deliberately carries only the structural fields the
        # PII-residue test allows. No email, no IP — that would defeat
        # the entire erasure pipeline.
        event = AuthAuditEventTable(
            user_id=user_id,
            event_type="user.erased",
            ip_address=None,
            user_agent=None,
            event_metadata={"user_id": str(user_id), "reason": reason},
            created_at=utc_now(),
        )
        session = _writer_session(writer)
        if session is None:
            with Session(self.engine, expire_on_commit=False) as own:
                own.add(event)
                own.commit()
            return
        session.add(event)


def _writer_session(writer: object) -> Session | None:
    session = getattr(writer, "session", None)
    if isinstance(session, Session):
        return session
    return None


def _scrub_audit_events_on_session(session: Session, user_id: UUID) -> None:
    """Strip PII columns and JSONB keys from the user's audit rows.

    The JSONB ``-`` operator is PostgreSQL-only, so the adapter reads
    the rows back on SQLite/test paths and rewrites the dict in place.
    Production paths run the bulk SQL in a single round trip.
    """
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        # One UPDATE strips both PII columns and three JSONB keys.
        session.execute(
            sa.text(
                "UPDATE auth_audit_events SET "
                "ip_address = NULL, "
                "user_agent = NULL, "
                "metadata = metadata - 'family_id' - 'ip_address' - 'user_agent' "
                "WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )
        return
    # Fallback path: SQLite test harness. Re-read each row, scrub the
    # JSON in Python, write it back.
    rows = session.exec(
        select(AuthAuditEventTable).where(
            cast(Any, AuthAuditEventTable.user_id == user_id)
        )
    ).all()
    for tup in rows:
        # SQLModel's ``exec(select(Table))`` yields ``Table`` instances
        # directly, but defensively unwrap a tuple in case the harness
        # ever swaps in a raw SQLAlchemy ``select``.
        row = tup[0] if isinstance(tup, tuple) else tup
        row.ip_address = None
        row.user_agent = None
        metadata = row.event_metadata
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        scrubbed: dict[str, Any] = {
            k: v for k, v in metadata.items() if k not in _PII_METADATA_KEYS
        }
        row.event_metadata = scrubbed
        session.add(row)


def _delete_artifacts_on_session(session: Session, user_id: UUID) -> None:
    session.execute(
        sa.delete(CredentialTable).where(cast(Any, CredentialTable.user_id == user_id))
    )
    session.execute(
        sa.delete(RefreshTokenTable).where(
            cast(Any, RefreshTokenTable.user_id == user_id)
        )
    )
    session.execute(
        sa.delete(AuthInternalTokenTable).where(
            cast(Any, AuthInternalTokenTable.user_id == user_id)
        )
    )
