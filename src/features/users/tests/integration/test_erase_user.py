"""Integration coverage for ``EraseUser`` against a real PostgreSQL.

Drives the GDPR Art. 17 pipeline end-to-end:

- The user row is scrubbed (email placeholder, ``is_erased=true``,
  ``last_login_at=NULL``, ``authz_version`` bumped, ``is_verified``
  preserved).
- ``auth_audit_events`` rows survive but lose ``ip_address``,
  ``user_agent``, and the ``family_id`` / ``ip_address`` /
  ``user_agent`` keys from their JSONB metadata.
- ``credentials`` / ``refresh_tokens`` / ``auth_internal_tokens`` rows
  for the user are gone.
- A ``delete_user_assets`` outbox row is staged in the same transaction.
- ``UserPort.get_by_id`` / ``get_by_email`` return ``None`` for the
  scrubbed user; a fresh registration can reclaim the original email.
- Re-running the use case on an already-erased user is a no-op.

Requires Docker for the testcontainer Postgres; the suite skips when
Docker is unavailable (matching the rest of the integration tree).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app_platform.shared.result import Ok
from features.authentication.adapters.outbound.auth_artifacts_cleanup import (
    SQLModelAuthArtifactsCleanupAdapter,
)
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    CredentialTable,
    RefreshTokenTable,
)
from features.outbox.adapters.outbound.sqlmodel.models import OutboxMessageTable
from features.outbox.adapters.outbound.sqlmodel.unit_of_work import (
    SQLModelOutboxUnitOfWork,
)
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from features.users.application.use_cases.erase_user import EraseUser

pytestmark = pytest.mark.integration


def _seed_user(engine: Engine, *, email: str = "subject@example.com") -> UUID:
    repo = SQLModelUserRepository(engine=engine)
    result = repo.create(email=email)
    assert isinstance(result, Ok)
    user_id = result.value.id
    # Seed credentials, refresh tokens, internal tokens, and an audit
    # event with PII metadata so the scrub has something to remove.
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            CredentialTable(user_id=user_id, algorithm="argon2", hash="dummy-hash")
        )
        session.add(
            RefreshTokenTable(
                user_id=user_id,
                token_hash="rt-hash",
                family_id=uuid4(),
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        session.add(
            AuthInternalTokenTable(
                user_id=user_id,
                purpose="password_reset",
                token_hash="it-hash",
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
        )
        session.add(
            AuthAuditEventTable(
                user_id=user_id,
                event_type="auth.login.succeeded",
                ip_address="1.2.3.4",
                user_agent="curl/1.0",
                event_metadata={
                    "family_id": str(uuid4()),
                    "ip_address": "1.2.3.4",
                    "user_agent": "curl/1.0",
                    "kept": "yes",
                },
            )
        )
        session.commit()
    return user_id


def _build_erase_user(engine: Engine) -> EraseUser:
    return EraseUser(
        _users=SQLModelUserRepository(engine=engine),
        _auth_artifacts=SQLModelAuthArtifactsCleanupAdapter(engine=engine),
        _outbox_uow=SQLModelOutboxUnitOfWork.from_engine(engine),
    )


def test_erase_scrubs_user_row_and_artifacts(postgres_users_engine: Engine) -> None:
    user_id = _seed_user(postgres_users_engine, email="scrub-me@example.com")
    use_case = _build_erase_user(postgres_users_engine)

    result = use_case.execute(user_id, "self_request")
    assert isinstance(result, Ok)

    repo = SQLModelUserRepository(engine=postgres_users_engine)
    # Filtered reads return None — the cached principal entry will
    # therefore resolve to "user not found" within the TTL.
    assert repo.get_by_id(user_id) is None
    assert repo.get_by_email("scrub-me@example.com") is None
    raw = repo.get_raw_by_id(user_id)
    assert raw is not None
    assert raw.is_erased is True
    assert raw.is_active is False
    assert raw.email == f"erased+{user_id}@erased.invalid"
    assert raw.last_login_at is None
    # authz_version bumped
    assert raw.authz_version >= 2

    with Session(postgres_users_engine) as session:
        # credentials / refresh / internal-token rows for the user are gone.
        creds = session.exec(
            select(CredentialTable).where(
                sa.cast(CredentialTable.user_id, sa.String) == str(user_id)
            )
        ).all()
        assert not creds
        refreshes = session.exec(
            select(RefreshTokenTable).where(
                sa.cast(RefreshTokenTable.user_id, sa.String) == str(user_id)
            )
        ).all()
        assert not refreshes
        internals = session.exec(
            select(AuthInternalTokenTable).where(
                sa.cast(AuthInternalTokenTable.user_id, sa.String) == str(user_id)
            )
        ).all()
        assert not internals
        # The audit row survived; its PII columns and JSONB keys are
        # cleared, except for the ``user.erased`` row we just inserted.
        events = [
            (r[0] if isinstance(r, tuple) else r)
            for r in session.exec(
                select(AuthAuditEventTable).where(
                    sa.cast(AuthAuditEventTable.user_id, sa.String) == str(user_id)
                )
            ).all()
        ]
        assert events, "Original audit row should still exist post-erasure"
        for row in events:
            metadata = row.event_metadata
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            assert "ip_address" not in metadata
            assert "user_agent" not in metadata
            assert "family_id" not in metadata
            if row.event_type != "user.erased":
                assert row.ip_address is None
                assert row.user_agent is None
                assert metadata.get("kept") == "yes"
        # And a ``user.erased`` audit row is present with no PII.
        erased_rows = [r for r in events if r.event_type == "user.erased"]
        assert len(erased_rows) == 1
        erased = erased_rows[0]
        meta = erased.event_metadata
        if isinstance(meta, str):
            meta = json.loads(meta)
        assert meta == {"user_id": str(user_id), "reason": "self_request"}
        # Outbox row for asset cleanup is staged.
        outbox_rows = [
            (r[0] if isinstance(r, tuple) else r)
            for r in session.exec(
                select(OutboxMessageTable).where(
                    OutboxMessageTable.job_name == "delete_user_assets"
                )
            ).all()
        ]
        assert outbox_rows
        assert any(r.payload.get("user_id") == str(user_id) for r in outbox_rows)


def test_erase_filters_email_lookup_and_allows_reuse(
    postgres_users_engine: Engine,
) -> None:
    user_id = _seed_user(postgres_users_engine, email="reusable@example.com")
    use_case = _build_erase_user(postgres_users_engine)
    use_case.execute(user_id, "self_request")

    repo = SQLModelUserRepository(engine=postgres_users_engine)
    assert repo.get_by_email("reusable@example.com") is None
    fresh = repo.create(email="reusable@example.com")
    assert isinstance(fresh, Ok)
    assert fresh.value.id != user_id


def test_erase_is_idempotent(postgres_users_engine: Engine) -> None:
    user_id = _seed_user(postgres_users_engine, email="twice@example.com")
    use_case = _build_erase_user(postgres_users_engine)
    use_case.execute(user_id, "self_request")
    # Second call: succeeds, but no new audit row, no new outbox row,
    # and the row stays in its post-erasure shape.
    pre_outbox = _count_outbox_rows(postgres_users_engine, "delete_user_assets")
    pre_erased_events = _count_events(postgres_users_engine, user_id, "user.erased")
    result = use_case.execute(user_id, "admin_request")
    assert isinstance(result, Ok)
    assert _count_outbox_rows(postgres_users_engine, "delete_user_assets") == pre_outbox
    assert (
        _count_events(postgres_users_engine, user_id, "user.erased")
        == pre_erased_events
    )


def test_post_erasure_pii_residue_scan(postgres_users_engine: Engine) -> None:
    """No row referencing the user holds the original email or IP."""
    original_email = "leaky@example.com"
    original_ip = "9.8.7.6"
    repo = SQLModelUserRepository(engine=postgres_users_engine)
    create = repo.create(email=original_email)
    assert isinstance(create, Ok)
    user_id = create.value.id
    with Session(postgres_users_engine, expire_on_commit=False) as session:
        session.add(
            CredentialTable(
                user_id=user_id, algorithm="argon2", hash="hash-with-no-pii"
            )
        )
        session.add(
            RefreshTokenTable(
                user_id=user_id,
                token_hash="rt-hash-clean",
                family_id=uuid4(),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_ip=original_ip,
                user_agent="ua/1.0",
            )
        )
        session.add(
            AuthAuditEventTable(
                user_id=user_id,
                event_type="auth.login.succeeded",
                ip_address=original_ip,
                user_agent="ua/1.0",
                event_metadata={"ip_address": original_ip, "kept": "no"},
            )
        )
        session.commit()
    _build_erase_user(postgres_users_engine).execute(user_id, "self_request")
    # Now scan every table the spec covers for residues of the
    # original email / IP linked to this user_id.
    with Session(postgres_users_engine) as session:
        # users: email is the placeholder, not the original.
        user_row = session.get(
            __import__(
                "features.users.adapters.outbound.persistence.sqlmodel.models",
                fromlist=["UserTable"],
            ).UserTable,
            user_id,
        )
        assert user_row is not None
        assert original_email not in user_row.email
        # credentials / refresh / internal token rows are gone, so they
        # cannot carry any residue.
        for table in (CredentialTable, RefreshTokenTable, AuthInternalTokenTable):
            rows = session.exec(
                select(table).where(sa.cast(table.user_id, sa.String) == str(user_id))
            ).all()
            assert not rows
        # Surviving audit rows must not mention the original IP/email.
        audit_rows = [
            (r[0] if isinstance(r, tuple) else r)
            for r in session.exec(
                select(AuthAuditEventTable).where(
                    sa.cast(AuthAuditEventTable.user_id, sa.String) == str(user_id)
                )
            ).all()
        ]
        for row in audit_rows:
            assert row.ip_address != original_ip
            meta = row.event_metadata
            if isinstance(meta, str):
                meta = json.loads(meta)
            assert original_ip not in json.dumps(meta)
            assert original_email not in json.dumps(meta)


def _count_outbox_rows(engine: Engine, job_name: str) -> int:
    with Session(engine) as session:
        rows = session.exec(
            select(OutboxMessageTable).where(OutboxMessageTable.job_name == job_name)
        ).all()
        return len(rows)


def _count_events(engine: Engine, user_id: UUID, event_type: str) -> int:
    with Session(engine) as session:
        rows = session.exec(
            select(AuthAuditEventTable).where(
                sa.cast(AuthAuditEventTable.user_id, sa.String) == str(user_id),
                AuthAuditEventTable.event_type == event_type,
            )
        ).all()
        return len(rows)
