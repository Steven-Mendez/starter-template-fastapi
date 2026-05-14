"""Integration coverage for atomic email-verification confirmation.

Two threads submitting the same email-verification token must
serialize on the row lock the use case takes via
``get_internal_token_for_update``. Exactly one thread succeeds, the
other receives ``TokenAlreadyUsedError``, and exactly one
``auth.email_verified`` audit event is recorded.
"""

from __future__ import annotations

import threading

import pytest
from sqlmodel import Session, select

import features.authentication.application.use_cases.auth.confirm_email_verification as cev_mod  # noqa: E501
from app_platform.config.settings import AppSettings
from app_platform.shared.result import Ok
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
)
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authentication.application.errors import TokenAlreadyUsedError
from features.authentication.composition.container import build_auth_container
from features.outbox.tests.fakes.fake_outbox import InlineDispatchOutboxUnitOfWork
from features.users.adapters.outbound.persistence.sqlmodel.models import UserTable
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SessionSQLModelUserRepository,
    SQLModelUserRepository,
)

pytestmark = pytest.mark.integration


def test_concurrent_email_verification_serializes_on_token_row(
    test_settings: AppSettings,
    postgres_auth_repository: SQLModelAuthRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_redis_url": None,
        }
    )
    users = SQLModelUserRepository(engine=postgres_auth_repository.engine)
    container = build_auth_container(
        settings=settings,
        users=users,
        outbox_uow=InlineDispatchOutboxUnitOfWork(dispatcher=lambda _n, _p: None),
        user_writer_factory=lambda session: SessionSQLModelUserRepository(
            session=session
        ),
        repository=postgres_auth_repository,
    )

    try:
        email = "verify-race@example.com"
        reg = container.register_user.execute(email=email, password="UserPassword123!")
        assert isinstance(reg, Ok)
        user_id = reg.value.id

        verify_request = container.request_email_verification.execute(user_id=user_id)
        assert isinstance(verify_request, Ok)
        token = verify_request.value.token
        assert token is not None

        # Gate the FIRST thread inside its transaction so the SECOND
        # thread reaches the FOR UPDATE lock and blocks on it. We
        # patch the use case's ``hash_token`` collaborator the same
        # way ``test_password_reset_atomicity`` patches
        # ``hash_password``: the first call blocks until the second
        # has had a chance to start.
        use_case = container.confirm_email_verification

        # The use case imports ``hash_token`` at module import time, so
        # the patch must target the module's binding. mypy can't see
        # the re-exported name; the runtime attribute is what
        # ``monkeypatch.setattr`` needs.
        original_hash = cev_mod.hash_token  # type: ignore[attr-defined]
        first_started = threading.Event()
        release_first = threading.Event()
        hash_calls: list[str] = []
        hash_calls_lock = threading.Lock()

        def gated_hash(t: str) -> str:
            with hash_calls_lock:
                hash_calls.append(threading.current_thread().name)
                call_number = len(hash_calls)
            if call_number == 1:
                first_started.set()
                assert release_first.wait(timeout=5)
            return original_hash(t)

        monkeypatch.setattr(cev_mod, "hash_token", gated_hash)

        successes: list[None] = []
        errors: list[Exception] = []

        def run_confirm() -> None:
            try:
                result = use_case.execute(token=token or "")
                match result:
                    case Ok():
                        successes.append(None)
                    case _ as err:
                        errors.append(err.error)
            except Exception as exc:
                errors.append(exc)

        first = threading.Thread(target=run_confirm, name="verify-1")
        second = threading.Thread(target=run_confirm, name="verify-2")

        first.start()
        assert first_started.wait(timeout=5)
        second.start()
        # Brief wait so the second thread reaches its own pre-tx hash.
        # The first thread is still blocked inside ``gated_hash`` and
        # has not yet acquired the row lock.
        release_first.set()

        first.join(timeout=5)
        second.join(timeout=5)
        assert not first.is_alive()
        assert not second.is_alive()
        assert len(successes) == 1
        assert len(errors) == 1
        assert isinstance(errors[0], TokenAlreadyUsedError)

        # Exactly one ``auth.email_verified`` audit event was recorded.
        with Session(
            postgres_auth_repository.engine, expire_on_commit=False
        ) as session:
            events = session.exec(
                select(AuthAuditEventTable).where(
                    AuthAuditEventTable.event_type == "auth.email_verified",
                    AuthAuditEventTable.user_id == user_id,
                )
            ).all()
            assert len(events) == 1
            # And the user is verified.
            user_row = session.exec(
                select(UserTable).where(UserTable.id == user_id)
            ).one()
            assert user_row.is_verified is True
    finally:
        container.shutdown()
