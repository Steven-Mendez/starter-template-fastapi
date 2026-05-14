"""outbox: add trace_context JSONB for W3C trace propagation

Revision ID: 20260520_0017
Revises: 20260519_0016
Create Date: 2026-05-20 00:00:00.000000

Adds ``outbox_messages.trace_context`` for the
``propagate-trace-context-through-jobs`` change. The producer side
(``SessionSQLModelOutboxAdapter.enqueue``) captures the active
``traceparent``/``tracestate`` carrier at enqueue time and persists it
into this column; the relay copies the column into the dispatched
payload under the reserved ``__trace`` key so the job entrypoint
(in-process or arq) can extract it and attach the context around the
handler call, unifying request -> outbox -> relay -> handler spans
into a single trace.

The column is ``NOT NULL DEFAULT '{}'::jsonb`` so legacy rows that
existed before this migration land have an empty carrier; the relay
tolerates empty maps (extract returns the current context, which
produces a fresh trace — same behavior as today).

Postgres 11+ stores a constant ``DEFAULT`` in ``pg_attribute`` without
rewriting the table, so this is a fast metadata-only ``ADD COLUMN``
even on a populated table. Per the one-way migration policy, this is
an additive change and ``downgrade`` simply drops the column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260520_0017"
down_revision: str | None = "20260519_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_messages",
        sa.Column(
            "trace_context",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("outbox_messages", "trace_context")
