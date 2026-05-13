"""Cross-feature relationship table for the ReBAC authorization engine.

The table is platform-owned because every feature that performs an
authorization check reads through it; pinning it to any one feature
would force that feature to leak across boundaries. The authorization
feature owns the SQL the rest of the code runs against this table; the
platform owns only the declarative schema.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""

    return datetime.now(UTC)


class RelationshipTable(SQLModel, table=True):
    """Zanzibar-style relationship tuple backing the ReBAC engine.

    Each row reads as ``{subject_type}:{subject_id}`` has relation
    ``{relation}`` on ``{resource_type}:{resource_id}``. Subjects are
    typed strings to leave room for non-user subjects (group sets,
    service accounts) without a schema migration.

    The unique constraint over the full tuple makes ``write_relationships``
    naturally idempotent: a duplicate write hits the constraint and the
    adapter swallows it. The two indexes drive the two read patterns:
    ``check`` / ``lookup_subjects`` (resource side) and ``lookup_resources``
    (subject side).
    """

    __tablename__ = "relationships"
    __table_args__ = (
        sa.UniqueConstraint(
            "resource_type",
            "resource_id",
            "relation",
            "subject_type",
            "subject_id",
            name="uq_relationships_tuple",
        ),
        sa.Index(
            "ix_relationships_resource",
            "resource_type",
            "resource_id",
            "relation",
        ),
        sa.Index(
            "ix_relationships_subject",
            "subject_type",
            "subject_id",
            "resource_type",
            "relation",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    resource_type: str = Field(nullable=False, max_length=50)
    resource_id: str = Field(nullable=False, max_length=64)
    relation: str = Field(nullable=False, max_length=50)
    subject_type: str = Field(nullable=False, max_length=50)
    subject_id: str = Field(nullable=False, max_length=64)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
