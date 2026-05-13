"""Two concurrent claim transactions see disjoint row sets.

Exercises the ``FOR UPDATE SKIP LOCKED`` semantics directly: open
transaction A, run the claim query, hold it open while transaction B
runs its own claim — B must observe only the rows A did not claim.
This is the property that lets multiple worker replicas share one
outbox table without coordinating.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelOutboxAdapter,
)

pytestmark = pytest.mark.integration

_CLAIM_QUERY = """
SELECT id
FROM   outbox_messages
WHERE  status = 'pending' AND available_at <= now()
ORDER  BY available_at
LIMIT  :limit
FOR    UPDATE SKIP LOCKED
"""


def _seed(engine: Engine, count: int) -> None:
    with Session(engine, expire_on_commit=False) as session:
        adapter = SessionSQLModelOutboxAdapter(_session=session)
        for i in range(count):
            adapter.enqueue(
                job_name="send_email",
                payload={"i": i},
            )
        session.commit()


def test_two_concurrent_claims_observe_disjoint_rows(
    postgres_outbox_engine: Engine,
) -> None:
    _seed(postgres_outbox_engine, count=4)
    now = datetime.now(timezone.utc)
    del now  # used only for clarity; the query embeds ``now()`` directly

    conn_a = postgres_outbox_engine.connect()
    conn_b = postgres_outbox_engine.connect()
    try:
        tx_a = conn_a.begin()
        tx_b = conn_b.begin()
        rows_a = list(conn_a.execute(text(_CLAIM_QUERY), {"limit": 2}).all())
        rows_b = list(conn_b.execute(text(_CLAIM_QUERY), {"limit": 4}).all())
        ids_a = {row.id for row in rows_a}
        ids_b = {row.id for row in rows_b}
        assert len(ids_a) == 2
        # A claimed two; B was offered four but only sees the other two
        # because A's rows are locked.
        assert len(ids_b) == 2
        assert ids_a.isdisjoint(ids_b)
        tx_a.rollback()
        tx_b.rollback()
    finally:
        conn_a.close()
        conn_b.close()
