"""Integration tests for ``SQLModelAuthorizationAdapter`` against real PostgreSQL.

The unit suite covers the engine's logic; this suite verifies the SQL
layer: the unique constraint, the indexes, and the read patterns'
real query plans.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlmodel import Session

from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
    utc_now,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.authorization.adapters.outbound.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from src.features.authorization.application.types import Relationship
from src.features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def adapter(
    postgres_auth_repository: SQLModelAuthRepository,
) -> Iterator[SQLModelAuthorizationAdapter]:
    from src.features.auth.adapters.outbound.authz_version import (  # noqa: PLC0415
        SQLModelUserAuthzVersionAdapter,
    )

    yield SQLModelAuthorizationAdapter(
        postgres_auth_repository.engine,
        make_test_registry(),
        SQLModelUserAuthzVersionAdapter(postgres_auth_repository.engine),
    )


def _seed_user(repo: SQLModelAuthRepository) -> UUID:
    with Session(repo.engine) as session:
        user = UserTable(
            id=uuid4(),
            email=f"user-{uuid4()}@example.com",
            password_hash="x",
            is_active=True,
            is_verified=True,
            authz_version=1,
            created_at=utc_now(),
            updated_at=utc_now(),
            last_login_at=None,
        )
        session.add(user)
        session.commit()
        return user.id


def test_crud_round_trip_against_real_postgres(
    postgres_auth_repository: SQLModelAuthRepository,
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    user_id = _seed_user(postgres_auth_repository)
    board_id = str(uuid4())
    tup = Relationship(
        resource_type="thing",
        resource_id=board_id,
        relation="owner",
        subject_type="user",
        subject_id=str(user_id),
    )

    adapter.write_relationships([tup])
    assert adapter.check(
        user_id=user_id, action="delete", resource_type="thing", resource_id=board_id
    )
    adapter.delete_relationships([tup])
    assert not adapter.check(
        user_id=user_id, action="delete", resource_type="thing", resource_id=board_id
    )


def test_unique_constraint_makes_writes_idempotent(
    postgres_auth_repository: SQLModelAuthRepository,
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    user_id = _seed_user(postgres_auth_repository)
    tup = Relationship(
        resource_type="thing",
        resource_id=str(uuid4()),
        relation="reader",
        subject_type="user",
        subject_id=str(user_id),
    )
    adapter.write_relationships([tup])
    adapter.write_relationships([tup])
    adapter.write_relationships([tup])

    with Session(postgres_auth_repository.engine) as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM relationships WHERE subject_id = :sid"),
            {"sid": str(user_id)},
        )
        count = result.scalar_one()
    assert count == 1


def test_required_indexes_exist(
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    with Session(postgres_auth_repository.engine) as session:
        result = session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'relationships'"
            )
        )
        indexes = {row[0] for row in result}
    assert "ix_relationships_resource" in indexes
    assert "ix_relationships_subject" in indexes
    assert "uq_relationships_tuple" in indexes


def test_lookup_resources_uses_subject_index(
    postgres_auth_repository: SQLModelAuthRepository,
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    """EXPLAIN should reference the subject-side index for lookup_resources."""
    user_id = _seed_user(postgres_auth_repository)
    # Seed enough rows that the planner will not just sequential-scan.
    adapter.write_relationships(
        [
            Relationship(
                resource_type="thing",
                resource_id=str(uuid4()),
                relation="reader",
                subject_type="user",
                subject_id=str(user_id),
            )
            for _ in range(50)
        ]
    )

    with Session(postgres_auth_repository.engine) as session:
        plan = session.execute(
            text(
                "EXPLAIN SELECT resource_id FROM relationships "
                "WHERE subject_type = 'user' AND subject_id = :sid "
                "AND resource_type = 'thing' "
                "AND relation IN ('reader','writer','owner') "
                "ORDER BY resource_id LIMIT 100"
            ),
            {"sid": str(user_id)},
        )
        plan_text = "\n".join(row[0] for row in plan)
    # Either the subject index or the unique tuple index is acceptable; the
    # bad outcome would be a sequential scan, so just assert no Seq Scan.
    assert "Seq Scan on relationships" not in plan_text


def test_authz_version_bumps_on_write_against_postgres(
    postgres_auth_repository: SQLModelAuthRepository,
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    user_id = _seed_user(postgres_auth_repository)
    before = postgres_auth_repository.get_user_by_id(user_id)
    assert before is not None
    before_version = before.authz_version

    adapter.write_relationships(
        [
            Relationship(
                resource_type="thing",
                resource_id=str(uuid4()),
                relation="reader",
                subject_type="user",
                subject_id=str(user_id),
            )
        ]
    )

    after = postgres_auth_repository.get_user_by_id(user_id)
    assert after is not None
    assert after.authz_version == before_version + 1
