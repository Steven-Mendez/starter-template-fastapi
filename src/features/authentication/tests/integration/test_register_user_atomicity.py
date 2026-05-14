"""Integration coverage for atomic user registration against PostgreSQL.

The three writes registration performs — the ``User`` row, the
``Credential`` row, and the ``auth.user_registered`` audit event —
must commit in a single transaction. A failure mid-chain must roll
back the user row so the email remains usable on a retry, mirroring
the unit-level coverage in ``tests/unit/test_register_user.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import pytest
from sqlmodel import Session, select

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Ok, Result
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    CredentialTable,
)
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRegisterUserTransactionPort,
)
from features.authentication.composition.container import build_auth_container
from features.authentication.domain.models import Credential
from features.outbox.tests.fakes.fake_outbox import InlineDispatchOutboxUnitOfWork
from features.users.adapters.outbound.persistence.sqlmodel.models import UserTable
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SessionSQLModelUserRepository,
    SQLModelUserRepository,
)
from features.users.application.errors import UserError
from features.users.domain.user import User

pytestmark = pytest.mark.integration


def test_registration_rollback_on_credential_write_failure_frees_email(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
) -> None:
    """A crash on ``upsert_credential`` rolls back the user row.

    Spec scenario "Credential write failure rolls back the user row":
    after the failure the email must be free for a retry — proved by
    verifying that no ``UserTable`` row survives and that a fresh
    registration with the same email succeeds.
    """
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_redis_url": None,
        }
    )
    users = SQLModelUserRepository(engine=postgres_auth_repository.engine)

    # Inject a session-scoped writer factory whose ``upsert_credential``
    # raises on the first call, then forwards on every subsequent
    # call. This lets the first registration attempt crash mid-tx
    # and the retry proceed normally.
    crashed_once: list[bool] = []

    class _ExplodingRegisterTx:
        """Wraps the real session writer to raise on credential upsert."""

        def __init__(self, inner: AuthRegisterUserTransactionPort) -> None:
            self._inner = inner

        def create_user(self, *, email: str) -> Result[User, UserError]:
            return self._inner.create_user(email=email)

        def upsert_credential(
            self, *, user_id: UUID, algorithm: str, hash: str
        ) -> Credential:
            if not crashed_once:
                crashed_once.append(True)
                raise RuntimeError(
                    "simulated credential write failure mid-registration"
                )
            return self._inner.upsert_credential(
                user_id=user_id, algorithm=algorithm, hash=hash
            )

        def record_audit_event(self, **kwargs: Any) -> None:
            return self._inner.record_audit_event(**kwargs)

    container = build_auth_container(
        settings=settings,
        users=users,
        outbox_uow=InlineDispatchOutboxUnitOfWork(dispatcher=lambda _n, _p: None),
        user_writer_factory=lambda session: SessionSQLModelUserRepository(
            session=session
        ),
        repository=postgres_auth_repository,
    )

    # Patch the repository's ``register_user_transaction`` so the
    # yielded writer is wrapped by ``_ExplodingRegisterTx``. The real
    # transaction still owns commit/rollback semantics — only the
    # writer surface is wrapped.
    original_tx = postgres_auth_repository.register_user_transaction

    @contextmanager
    def _patched_tx() -> Iterator[_ExplodingRegisterTx]:
        with original_tx() as inner:
            yield _ExplodingRegisterTx(inner)

    postgres_auth_repository.register_user_transaction = _patched_tx  # type: ignore[method-assign, assignment]

    try:
        email = "register-rollback@example.com"
        # First attempt explodes; the user row must roll back.
        with pytest.raises(RuntimeError, match="simulated credential write"):
            container.register_user.execute(email=email, password="UserPassword123!")

        # Verify the rollback at the database level.
        with Session(
            postgres_auth_repository.engine, expire_on_commit=False
        ) as session:
            assert (
                session.exec(select(UserTable).where(UserTable.email == email)).first()
                is None
            )
            assert (
                session.exec(
                    select(AuthAuditEventTable).where(
                        AuthAuditEventTable.event_type == "auth.user_registered"
                    )
                ).first()
                is None
            )

        # Restore the original transaction and retry; the email must
        # be free.
        postgres_auth_repository.register_user_transaction = original_tx  # type: ignore[method-assign]
        retry = container.register_user.execute(
            email=email, password="UserPassword123!"
        )
        assert isinstance(retry, Ok)

        with Session(
            postgres_auth_repository.engine, expire_on_commit=False
        ) as session:
            user_row = session.exec(
                select(UserTable).where(UserTable.email == email)
            ).one()
            assert user_row.email == email
            cred_row = session.exec(
                select(CredentialTable).where(CredentialTable.user_id == user_row.id)
            ).one()
            assert cred_row.hash.startswith("$argon2")
    finally:
        container.shutdown()
