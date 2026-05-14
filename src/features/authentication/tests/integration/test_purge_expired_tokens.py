"""Integration coverage for ``PurgeExpiredTokens`` against PostgreSQL.

The use case sweeps two append-only tables — ``refresh_tokens`` and
``auth_internal_tokens`` — in 10k-row batches so neither one grows
without bound. The cases below pin four behaviours required by the
``schedule-token-cleanup`` spec:

* expired refresh-token rows past the retention window are deleted,
* expired internal-token rows past the retention window are deleted,
* rows still inside the retention window survive a purge,
* the batched DELETE loop drains a set larger than the 10k batch
  ceiling.

These tests must run against PostgreSQL because the repository
implementation uses Postgres-flavoured ``DELETE ... WHERE id IN
(SELECT ... LIMIT N)`` and the per-batch transaction relies on
Postgres semantics for the row-count return.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from app_platform.shared.result import Ok
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authentication.application.use_cases.maintenance import (
    PurgeExpiredTokens,
    PurgeReport,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _seed_user(engine: Engine, *, email: str) -> UUID:
    """Insert a minimal ``users`` row and return its id.

    The token tables both reference ``users.id`` via a NOT NULL foreign
    key, so every seeded token row needs a parent user. The fields not
    populated here have database defaults or are nullable.
    """
    user_id = uuid4()
    now = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO users (
                    id, email, is_active, is_verified, is_erased,
                    authz_version, created_at, updated_at
                ) VALUES (
                    :id, :email, true, false, false,
                    1, :created_at, :updated_at
                )
                """
            ),
            {
                "id": str(user_id),
                "email": email,
                "created_at": now,
                "updated_at": now,
            },
        )
    return user_id


def _bulk_insert_refresh_tokens(
    engine: Engine,
    *,
    user_id: UUID,
    count: int,
    expires_at: datetime,
    revoked_at: datetime | None = None,
) -> None:
    """Bulk-insert ``count`` refresh-token rows for the given user.

    The seeding intentionally bypasses the repository helper methods so
    we can set ``expires_at`` and ``revoked_at`` to past dates directly
    (the repository's ``create_refresh_token`` rejects expirations in
    the past).
    """
    now = datetime.now(UTC)
    rows = [
        {
            "id": str(uuid4()),
            "user_id": str(user_id),
            "token_hash": f"refresh-{user_id}-{i}-{uuid4().hex}",
            "family_id": str(uuid4()),
            "expires_at": expires_at,
            "revoked_at": revoked_at,
            "replaced_by_token_id": None,
            "created_at": now,
            "created_ip": None,
            "user_agent": None,
        }
        for i in range(count)
    ]
    # Chunk inserts to keep the parameter count well under Postgres' 65535 cap.
    chunk_size = 1000
    with engine.begin() as conn:
        for start in range(0, len(rows), chunk_size):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO refresh_tokens (
                        id, user_id, token_hash, family_id, expires_at,
                        revoked_at, replaced_by_token_id, created_at,
                        created_ip, user_agent
                    ) VALUES (
                        :id, :user_id, :token_hash, :family_id, :expires_at,
                        :revoked_at, :replaced_by_token_id, :created_at,
                        :created_ip, :user_agent
                    )
                    """
                ),
                rows[start : start + chunk_size],
            )


def _bulk_insert_internal_tokens(
    engine: Engine,
    *,
    user_id: UUID,
    count: int,
    purpose: str,
    expires_at: datetime,
    used_at: datetime | None = None,
) -> None:
    """Bulk-insert ``count`` internal-token rows for the given user."""
    now = datetime.now(UTC)
    rows = [
        {
            "id": str(uuid4()),
            "user_id": str(user_id),
            "purpose": purpose,
            "token_hash": f"internal-{user_id}-{i}-{uuid4().hex}",
            "expires_at": expires_at,
            "used_at": used_at,
            "created_at": now,
            "created_ip": None,
        }
        for i in range(count)
    ]
    chunk_size = 1000
    with engine.begin() as conn:
        for start in range(0, len(rows), chunk_size):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO auth_internal_tokens (
                        id, user_id, purpose, token_hash, expires_at,
                        used_at, created_at, created_ip
                    ) VALUES (
                        :id, :user_id, :purpose, :token_hash, :expires_at,
                        :used_at, :created_at, :created_ip
                    )
                    """
                ),
                rows[start : start + chunk_size],
            )


_COUNT_SQL: dict[str, str] = {
    "refresh_tokens": "SELECT COUNT(*) FROM refresh_tokens",
    "auth_internal_tokens": "SELECT COUNT(*) FROM auth_internal_tokens",
}


def _count(engine: Engine, table: str) -> int:
    # Allow-list table names to keep the count helper free of dynamic SQL.
    sql = _COUNT_SQL[table]
    with engine.connect() as conn:
        result = conn.execute(sa.text(sql))
        return int(result.scalar_one())


# ---------------------------------------------------------------------------
# Tests — one per acceptance criterion in tasks.md §4
# ---------------------------------------------------------------------------


def test_purge_deletes_all_expired_refresh_tokens(
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    """Tasks 4.1 — 1000 expired refresh-token rows must all be gone.

    Each row has ``expires_at = now() - 30 days``, well past the 7-day
    retention window. After a single purge tick the table must be
    empty and the report must reflect 1000 deletions.
    """
    engine = postgres_auth_repository.engine
    user_id = _seed_user(engine, email="purge-refresh@example.com")
    expired = datetime.now(UTC) - timedelta(days=30)
    _bulk_insert_refresh_tokens(engine, user_id=user_id, count=1000, expires_at=expired)
    assert _count(engine, "refresh_tokens") == 1000

    use_case = PurgeExpiredTokens(_repository=postgres_auth_repository)
    result = use_case.execute(retention_days=7)

    assert isinstance(result, Ok)
    report: PurgeReport = result.value
    assert report.refresh_tokens_deleted == 1000
    assert report.internal_tokens_deleted == 0
    assert _count(engine, "refresh_tokens") == 0


def test_purge_deletes_all_expired_internal_tokens(
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    """Tasks 4.2 — 500 used internal-token rows older than retention must be gone.

    Each row carries ``used_at = now() - 30 days``. ``expires_at`` is
    set in the past as well so the row matches the eligibility set on
    either clause; in production these are equivalent for the purge.
    """
    engine = postgres_auth_repository.engine
    user_id = _seed_user(engine, email="purge-internal@example.com")
    long_ago = datetime.now(UTC) - timedelta(days=30)
    _bulk_insert_internal_tokens(
        engine,
        user_id=user_id,
        count=500,
        purpose="password_reset",
        expires_at=long_ago,
        used_at=long_ago,
    )
    assert _count(engine, "auth_internal_tokens") == 500

    use_case = PurgeExpiredTokens(_repository=postgres_auth_repository)
    result = use_case.execute(retention_days=7)

    assert isinstance(result, Ok)
    report: PurgeReport = result.value
    assert report.internal_tokens_deleted == 500
    assert report.refresh_tokens_deleted == 0
    assert _count(engine, "auth_internal_tokens") == 0


def test_purge_preserves_rows_within_retention_window(
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    """Tasks 4.3 — rows still inside the retention window must survive.

    Mixes recently-expired and unexpired rows in both tables. ``expires_at
    = now() - 1 day`` sits inside the 7-day window so those rows are
    not eligible for deletion. We also seed rows with ``expires_at`` in
    the future to guard against an off-by-one that would treat a still-
    live token as eligible.
    """
    engine = postgres_auth_repository.engine
    user_id = _seed_user(engine, email="purge-survivors@example.com")

    one_day_ago = datetime.now(UTC) - timedelta(days=1)
    future = datetime.now(UTC) + timedelta(days=14)

    # Refresh tokens: 10 expired 1 day ago, 10 still valid in the future.
    _bulk_insert_refresh_tokens(
        engine, user_id=user_id, count=10, expires_at=one_day_ago
    )
    _bulk_insert_refresh_tokens(engine, user_id=user_id, count=10, expires_at=future)

    # Internal tokens: 10 used 1 day ago, 10 unused with future expiry.
    _bulk_insert_internal_tokens(
        engine,
        user_id=user_id,
        count=10,
        purpose="password_reset",
        expires_at=future,
        used_at=one_day_ago,
    )
    _bulk_insert_internal_tokens(
        engine,
        user_id=user_id,
        count=10,
        purpose="email_verify",
        expires_at=future,
        used_at=None,
    )

    assert _count(engine, "refresh_tokens") == 20
    assert _count(engine, "auth_internal_tokens") == 20

    use_case = PurgeExpiredTokens(_repository=postgres_auth_repository)
    result = use_case.execute(retention_days=7)

    assert isinstance(result, Ok)
    report: PurgeReport = result.value
    assert report.refresh_tokens_deleted == 0
    assert report.internal_tokens_deleted == 0
    assert _count(engine, "refresh_tokens") == 20
    assert _count(engine, "auth_internal_tokens") == 20


def test_purge_drains_set_larger_than_single_batch(
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    """Tasks 4.4 — > 10000 expired rows must all be deleted across batches.

    The repository deletes in 10k-row chunks and loops until the
    eligibility set is empty. Seeding 10500 expired rows forces at
    least two iterations of the loop; if the implementation forgot to
    loop, ~500 rows would remain and this test would fail loudly.
    """
    engine = postgres_auth_repository.engine
    user_id = _seed_user(engine, email="purge-batch@example.com")
    expired = datetime.now(UTC) - timedelta(days=30)

    seeded = 10500
    _bulk_insert_refresh_tokens(
        engine, user_id=user_id, count=seeded, expires_at=expired
    )
    assert _count(engine, "refresh_tokens") == seeded

    use_case = PurgeExpiredTokens(_repository=postgres_auth_repository)
    result = use_case.execute(retention_days=7)

    assert isinstance(result, Ok)
    report: PurgeReport = result.value
    assert report.refresh_tokens_deleted == seeded
    assert _count(engine, "refresh_tokens") == 0
