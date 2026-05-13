"""Handler-side dedup helper for outbox-fed jobs.

The relay is at-least-once: a worker crash between
``JobQueuePort.enqueue`` and the per-row ``mark_delivered`` commit can
cause the next tick to re-deliver the row. Handlers MUST be idempotent
on the relay's reserved ``__outbox_message_id`` payload key; this
module is the canonical implementation of that idempotency check —
"have I already processed this id?" — backed by the
``processed_outbox_messages`` table.

The returned callable takes a message-id string and returns ``True``
on first observation (the handler should run the side effect),
``False`` on subsequent observations (the handler MUST short-circuit
to ``Ok``). The callable opens its own short transaction per call.

This lives in ``composition`` (not ``adapters``) because it depends on
both the SQL engine and the outbox model — the same wiring layer
where the engine is constructed. Handlers from other features import
the callable type alias from their own feature's ``composition.jobs``
module and never reach into outbox internals.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.models import (
    ProcessedOutboxMessageTable,
)


def build_handler_dedupe(engine: Engine) -> Callable[[str], bool]:
    """Build a callable that records (or detects) processed outbox ids.

    The returned function takes the ``__outbox_message_id`` payload
    value and:

    - Returns ``True`` when it successfully inserts a new dedup row
      (first observation; the handler should run the side effect).
    - Returns ``False`` when the insert raises a PK collision (the
      id was already processed; the handler MUST short-circuit).

    Any malformed message id (non-UUID) is treated as "not deduped"
    and the handler runs as if no dedup were wired — this keeps the
    seam safe when tests or legacy producers enqueue without the
    reserved key in the documented shape.
    """

    def _dedupe(message_id: str) -> bool:
        try:
            row_id = UUID(message_id)
        except (TypeError, ValueError):
            # The reserved key was present but malformed; fall back to
            # the no-dedup path so the handler still runs.
            return True
        with Session(engine, expire_on_commit=False) as session:
            try:
                session.add(ProcessedOutboxMessageTable(id=row_id))
                session.commit()
            except IntegrityError:
                session.rollback()
                return False
            except sa.exc.SQLAlchemyError:
                # Don't swallow unexpected DB errors — let the handler
                # treat the job as failed so arq retries.
                session.rollback()
                raise
            return True

    return _dedupe
