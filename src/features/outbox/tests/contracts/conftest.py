"""Re-export the outbox testcontainers Postgres fixture into the contracts dir.

The :class:`OutboxPort` contract suite parametrises its scenarios over
both the in-memory fake and the real :class:`SessionSQLModelOutboxAdapter`,
so it needs the same ``postgres_outbox_engine`` fixture the integration
tests use. Re-exporting via ``noqa: F401`` keeps the fixture defined in
exactly one place (``../integration/conftest.py``) while making it
visible to pytest's resolver inside ``tests/contracts/``.
"""

from __future__ import annotations

from features.outbox.tests.integration.conftest import (  # noqa: F401
    _outbox_postgres_url,
    postgres_outbox_engine,
)
