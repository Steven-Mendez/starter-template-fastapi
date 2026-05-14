"""SQLModel tables backing the transactional outbox.

A producer transaction inserts one row per side effect; the relay loop
running inside the worker consumes them by claim-and-update under
``FOR UPDATE SKIP LOCKED`` semantics. The partial index on
``status='pending'`` keeps the claim scan cheap once delivered rows
accumulate, since the index only contains rows the relay can act on.

Two tables live in this module:

- :class:`OutboxMessageTable` — the producer-written queue.
- :class:`ProcessedOutboxMessageTable` — the handler-side dedup table.
  Handlers insert ``id`` (the source ``OutboxMessage.id``) inside their
  own transaction; a duplicate-PK collision is the signal that this
  message was already processed and the handler MUST short-circuit to
  ``Ok``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlmodel import Column, Field, SQLModel


def _utc_now() -> datetime:
    """Return the current UTC instant as a timezone-aware datetime."""

    return datetime.now(UTC)


class OutboxMessageTable(SQLModel, table=True):
    """A pending or delivered outbox row.

    The ``status`` column is a free-text discriminator that the relay
    flips between ``pending``, ``delivered``, and ``failed`` — encoded
    as plain text rather than a Postgres enum to avoid migrations when
    adding a new state (none planned, but starter code stays flexible).
    """

    __tablename__ = "outbox_messages"
    __table_args__ = (
        sa.Index(
            "ix_outbox_pending",
            "available_at",
            "id",
            postgresql_where=sa.text("status = 'pending'"),
        ),
        sa.Index("ix_outbox_created", "created_at"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(
            postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
    )
    job_name: str = Field(sa_column=Column(sa.String(length=128), nullable=False))
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
        ),
    )
    trace_context: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    available_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(sa.DateTime(timezone=True), nullable=False),
    )
    status: str = Field(
        default="pending",
        sa_column=Column(
            sa.String(length=16), nullable=False, server_default="pending"
        ),
    )
    attempts: int = Field(
        default=0,
        sa_column=Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    last_error: str | None = Field(
        default=None,
        sa_column=Column(sa.Text, nullable=True),
    )
    locked_at: datetime | None = Field(
        default=None,
        sa_column=Column(sa.DateTime(timezone=True), nullable=True),
    )
    locked_by: str | None = Field(
        default=None,
        sa_column=Column(sa.String(length=128), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(sa.DateTime(timezone=True), nullable=False),
    )
    delivered_at: datetime | None = Field(
        default=None,
        sa_column=Column(sa.DateTime(timezone=True), nullable=True),
    )
    failed_at: datetime | None = Field(
        default=None,
        sa_column=Column(sa.DateTime(timezone=True), nullable=True),
    )


class ProcessedOutboxMessageTable(SQLModel, table=True):
    """Handler-side dedup record for an already-processed outbox message.

    Handlers insert a row keyed on ``OutboxMessage.id`` inside their
    own transaction. A duplicate-PK collision means the message was
    already processed; the handler MUST treat that as ``Ok`` and skip
    re-running the side effect. This makes the at-least-once relay
    safe even when the destination side effect (sending email, writing
    to an external API) is not naturally idempotent.
    """

    __tablename__ = "processed_outbox_messages"

    id: UUID = Field(
        sa_column=Column(
            postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
    )
    processed_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
