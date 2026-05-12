"""SQLModel table definitions for the authentication feature.

These mappings own the database schema for refresh tokens, internal
(single-use) tokens, and the auth audit log. The ``users`` table is
owned by the users feature (``src.features.users``); authentication
references it only through the ``user_id`` foreign key.

The ``relationships`` table that drives the ReBAC authorization engine
lives in ``src/platform/persistence/sqlmodel/authorization/`` because
every feature reads it at request time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


class CredentialTable(SQLModel, table=True):
    """Password credential row owned by the authentication feature.

    A user can hold at most one credential per algorithm — the unique
    constraint on ``(user_id, algorithm)`` is what permits passkey or
    OAuth credentials to be added later as new rows without reshaping
    the schema. This table is the sole source of truth for password
    hashes; the ``users`` table no longer carries a ``password_hash``
    column.
    """

    __tablename__ = "credentials"
    __table_args__ = (
        sa.UniqueConstraint(
            "user_id", "algorithm", name="uq_credentials_user_id_algorithm"
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        foreign_key="users.id", index=True, nullable=False, ondelete="CASCADE"
    )
    algorithm: str = Field(nullable=False)
    hash: str = Field(nullable=False)
    last_changed_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class RefreshTokenTable(SQLModel, table=True):
    """Refresh token row.

    Stores only the SHA-256 hash of the token so a database dump never
    exposes bearer credentials. ``family_id`` groups every token issued
    from a single login chain so reuse detection can revoke the whole
    family at once. ``replaced_by_token_id`` keeps an audit chain back to
    the original login without persisting the raw token values.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        foreign_key="users.id", index=True, nullable=False, ondelete="CASCADE"
    )
    token_hash: str = Field(index=True, nullable=False)
    family_id: UUID = Field(index=True, nullable=False)
    expires_at: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True)
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    replaced_by_token_id: UUID | None = Field(
        default=None, foreign_key="refresh_tokens.id", ondelete="SET NULL"
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    created_ip: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)


class AuthAuditEventTable(SQLModel, table=True):
    """Append-only audit log row for any auth/authz-relevant action."""

    __tablename__ = "auth_audit_events"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(
        default=None, foreign_key="users.id", index=True, ondelete="SET NULL"
    )
    event_type: str = Field(index=True, nullable=False)
    ip_address: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    event_metadata: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column(
            "metadata",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
        ),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True),
    )


class AuthInternalTokenTable(SQLModel, table=True):
    """Single-use, short-lived token used for password resets and email verification.

    Living in a dedicated table keeps the flow decoupled from the actual
    email delivery infrastructure and makes expiry and usage auditing
    trivial: the ``used_at`` timestamp is the consumption marker.
    """

    __tablename__ = "auth_internal_tokens"
    __table_args__ = (
        sa.UniqueConstraint("token_hash", name="uq_auth_internal_tokens_hash"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(
        default=None, foreign_key="users.id", index=True, ondelete="CASCADE"
    )
    purpose: str = Field(index=True, nullable=False)
    token_hash: str = Field(index=True, nullable=False)
    expires_at: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True)
    )
    used_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    created_ip: str | None = Field(default=None)


__all__ = [
    "AuthAuditEventTable",
    "AuthInternalTokenTable",
    "CredentialTable",
    "RefreshTokenTable",
    "utc_now",
]
