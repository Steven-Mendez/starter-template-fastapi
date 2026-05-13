"""Integration tests for ``SQLModelAuthorizationAdapter`` against real PostgreSQL.

The unit suite covers the engine's logic; this suite verifies the SQL
layer: the unique constraint, the indexes, and the read patterns'
real query plans.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlmodel import Session

from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authorization.adapters.outbound.sqlmodel import (
    SQLModelAuthorizationAdapter,
)
from features.authorization.application.types import Relationship
from features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)
from features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
    utc_now,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def adapter(
    postgres_auth_repository: SQLModelAuthRepository,
) -> SQLModelAuthorizationAdapter:
    from features.users.adapters.outbound.authz_version import (
        SQLModelUserAuthzVersionAdapter,
    )

    return SQLModelAuthorizationAdapter(
        postgres_auth_repository.engine,
        make_test_registry(),
        SQLModelUserAuthzVersionAdapter(postgres_auth_repository.engine),
    )


def _seed_user(repo: SQLModelAuthRepository) -> UUID:
    with Session(repo.engine) as session:
        user = UserTable(
            id=uuid4(),
            email=f"user-{uuid4()}@example.com",
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
    from features.users.adapters.outbound.persistence.sqlmodel.repository import (
        SQLModelUserRepository,
    )

    user_id = _seed_user(postgres_auth_repository)
    users = SQLModelUserRepository(engine=postgres_auth_repository.engine)
    before = users.get_by_id(user_id)
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

    after = users.get_by_id(user_id)
    assert after is not None
    assert after.authz_version == before_version + 1


def test_write_relationships_atomic_bump_visible_from_fresh_connection(
    postgres_auth_repository: SQLModelAuthRepository,
    adapter: SQLModelAuthorizationAdapter,
) -> None:
    """Happy path: a successful write commits the row and the bump together.

    Both must be visible to a fresh connection opened after the call
    returns, demonstrating that the bump landed in the same commit as
    the relationship row rather than as a follow-up second transaction.
    """
    user_id = _seed_user(postgres_auth_repository)
    board_id = str(uuid4())

    adapter.write_relationships(
        [
            Relationship(
                resource_type="thing",
                resource_id=board_id,
                relation="reader",
                subject_type="user",
                subject_id=str(user_id),
            )
        ]
    )

    with Session(postgres_auth_repository.engine) as session:
        rel_count = session.execute(
            text(
                "SELECT COUNT(*) FROM relationships "
                "WHERE resource_type = 'thing' AND resource_id = :rid "
                "AND subject_id = :sid"
            ),
            {"rid": board_id, "sid": str(user_id)},
        ).scalar_one()
        bumped_version = session.execute(
            text("SELECT authz_version FROM users WHERE id = :uid"),
            {"uid": str(user_id)},
        ).scalar_one()
    assert rel_count == 1
    # Seeded value is 1; the bump should have produced 2.
    assert bumped_version == 2


def test_bump_failure_rolls_back_relationship_write(
    postgres_auth_repository: SQLModelAuthRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forced failure on ``bump_in_session`` rolls back the relationship row.

    Patches the SQLModel adapter's ``bump_in_session`` to raise; asserts
    that the relationship row never lands and the user's
    ``authz_version`` stays at its seeded value when read from a fresh
    connection.
    """
    from features.users.adapters.outbound.authz_version import (
        SQLModelUserAuthzVersionAdapter,
    )

    engine = postgres_auth_repository.engine
    user_id = _seed_user(postgres_auth_repository)
    board_id = str(uuid4())

    version_adapter = SQLModelUserAuthzVersionAdapter(engine)

    def _boom(session: object, user_id: UUID) -> None:
        del session, user_id
        raise RuntimeError("forced bump failure")

    monkeypatch.setattr(version_adapter, "bump_in_session", _boom)

    adapter = SQLModelAuthorizationAdapter(
        engine, make_test_registry(), version_adapter
    )

    with pytest.raises(RuntimeError, match="forced bump failure"):
        adapter.write_relationships(
            [
                Relationship(
                    resource_type="thing",
                    resource_id=board_id,
                    relation="reader",
                    subject_type="user",
                    subject_id=str(user_id),
                )
            ]
        )

    with Session(engine) as session:
        rel_count = session.execute(
            text(
                "SELECT COUNT(*) FROM relationships "
                "WHERE resource_type = 'thing' AND resource_id = :rid "
                "AND subject_id = :sid"
            ),
            {"rid": board_id, "sid": str(user_id)},
        ).scalar_one()
        version = session.execute(
            text("SELECT authz_version FROM users WHERE id = :uid"),
            {"uid": str(user_id)},
        ).scalar_one()
    assert rel_count == 0
    # The seed value is 1; nothing should have committed.
    assert version == 1
