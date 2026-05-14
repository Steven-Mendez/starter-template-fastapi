"""Composition root for the users feature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.background_jobs.application.ports.job_queue_port import JobQueuePort
from features.file_storage.application.ports.file_storage_port import FileStoragePort
from features.outbox.application.ports.outbox_uow_port import OutboxUnitOfWorkPort
from features.users.adapters.outbound.authz_version import (
    SQLModelUserAuthzVersionAdapter,
)
from features.users.adapters.outbound.file_storage_user_assets import (
    FileStorageUserAssetsAdapter,
)
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SessionSQLModelUserRepository,
    SQLModelUserRepository,
)
from features.users.adapters.outbound.user_registrar import (
    SQLModelUserRegistrarAdapter,
)
from features.users.application.ports.auth_artifacts_cleanup_port import (
    AuthArtifactsCleanupPort,
)
from features.users.application.ports.credential_writer_port import (
    CredentialWriterPort,
)
from features.users.application.ports.user_assets_cleanup_port import (
    UserAssetsCleanupPort,
)
from features.users.application.ports.user_audit_reader_port import (
    UserAuditReaderPort,
)
from features.users.application.use_cases.deactivate_user import DeactivateUser
from features.users.application.use_cases.erase_user import EraseUser
from features.users.application.use_cases.export_user_data import ExportUserData
from features.users.application.use_cases.get_user_by_email import (
    GetUserByEmail,
)
from features.users.application.use_cases.get_user_by_id import GetUserById
from features.users.application.use_cases.list_users import ListUsers
from features.users.application.use_cases.register_user import RegisterUser
from features.users.application.use_cases.update_profile import UpdateProfile

# Verifies a user's current password — used to gate ``DELETE /me/erase``
# against a stolen access token. Returns ``True`` when the password
# matches the stored credential. Implemented in the authentication
# feature and wired in via :meth:`UsersContainer.wire_password_verifier`.
PasswordVerifier = Callable[[UUID, str], bool]


@dataclass(slots=True)
class UsersContainer:
    """Bundle of singletons for the users feature."""

    user_repository: SQLModelUserRepository
    user_authz_version_adapter: SQLModelUserAuthzVersionAdapter
    user_assets_cleanup: UserAssetsCleanupPort
    register_user: RegisterUser
    get_user_by_id: GetUserById
    get_user_by_email: GetUserByEmail
    update_profile: UpdateProfile
    deactivate_user: DeactivateUser
    list_users: ListUsers
    erase_user: EraseUser | None = None
    export_user_data: ExportUserData | None = None
    # Optional collaborator injected by the auth container at composition
    # time; the HTTP route reads it to gate ``DELETE /me/erase`` on
    # current-password re-auth.
    password_verifier: PasswordVerifier | None = None
    # ``JobQueuePort`` injected at composition; the erase routes enqueue
    # an ``erase_user`` job (via the in-process queue in tests / arq in
    # production) and return ``202 Accepted`` while the worker runs the
    # actual scrub. Kept optional so unit tests can construct the
    # container without a queue.
    job_queue: JobQueuePort | None = None

    def shutdown(self) -> None:
        # The engine is shared with the authentication container; it is
        # disposed there. Nothing per-feature to release.
        return None

    def wire_erase_user(
        self,
        *,
        auth_artifacts: AuthArtifactsCleanupPort,
        audit_reader: UserAuditReaderPort,
        outbox_uow: OutboxUnitOfWorkPort,
        file_storage: FileStoragePort,
    ) -> None:
        """Wire the erase/export use cases now that auth-side ports exist.

        The ``EraseUser`` and ``ExportUserData`` use cases need
        authentication-side collaborators (the artifacts-cleanup
        adapter that scrubs ``auth_audit_events`` / ``credentials`` /
        ``refresh_tokens`` / ``auth_internal_tokens``, and the audit
        reader that lists the user's history). Those adapters are only
        constructible after the auth container exists, so the users
        container starts without them and the composition root attaches
        them here.
        """
        self.erase_user = EraseUser(
            _users=self.user_repository,
            _auth_artifacts=auth_artifacts,
            _outbox_uow=outbox_uow,
        )
        self.export_user_data = ExportUserData(
            _users=self.user_repository,
            _file_storage=file_storage,
            _audit_reader=audit_reader,
        )

    def wire_password_verifier(self, verifier: PasswordVerifier) -> None:
        """Inject the auth-side password verifier for ``DELETE /me/erase``."""
        self.password_verifier = verifier

    def wire_job_queue(self, job_queue: JobQueuePort) -> None:
        """Inject the job-queue port the erase routes enqueue against."""
        self.job_queue = job_queue

    def session_user_writer_factory(
        self,
    ) -> Callable[[Session], SessionSQLModelUserRepository]:
        """Return a factory binding a session-scoped ``UserPort`` adapter.

        Passed into the auth repository so the registration and
        internal-token transactions write the ``User`` row on the
        same session as their own writes. The composition root threads
        this factory through to ``build_auth_container(...)``.
        """
        return lambda session: SessionSQLModelUserRepository(session=session)

    def wire_refresh_token_revoker(
        self, revoke_all_refresh_tokens: Callable[[UUID], None]
    ) -> None:
        """Wire the authentication-side refresh-token revoker into deactivate.

        Called from the composition root once the authentication container
        exists. ``DELETE /me`` is a synchronous user action whose response
        must reflect a revoked refresh-token family on the server; the
        collaborator is invoked inline by :class:`DeactivateUser` inside the
        same Unit of Work that flips ``is_active=False``. The contract is a
        plain callable so ``users`` stays decoupled from the authentication
        use-case type (import-linter forbids ``users -> authentication``).
        """
        self.deactivate_user._revoke_all_refresh_tokens = revoke_all_refresh_tokens


def build_users_container(
    *,
    engine: Engine,
    file_storage: FileStoragePort,
    outbox_uow: OutboxUnitOfWorkPort | None = None,
) -> UsersContainer:
    """Construct the users container sharing the auth engine.

    ``file_storage`` provides the per-user asset prefix cleanup; the
    adapter is built unconditionally so the worker can resolve the port
    even when no storage-using feature is wired yet (the default
    cleanup walks ``users/{user_id}/`` and is a no-op when no blobs
    exist). ``outbox_uow`` is optional so unit tests that exercise the
    use case without a real outbox still construct the container.
    """
    repository = SQLModelUserRepository(engine=engine)
    authz_version_adapter = SQLModelUserAuthzVersionAdapter(engine)
    user_assets_cleanup = FileStorageUserAssetsAdapter(_storage=file_storage)
    return UsersContainer(
        user_repository=repository,
        user_authz_version_adapter=authz_version_adapter,
        user_assets_cleanup=user_assets_cleanup,
        register_user=RegisterUser(_users=repository),
        get_user_by_id=GetUserById(_users=repository),
        get_user_by_email=GetUserByEmail(_users=repository),
        update_profile=UpdateProfile(_users=repository),
        deactivate_user=DeactivateUser(_users=repository, _outbox_uow=outbox_uow),
        list_users=ListUsers(_users=repository),
    )


def build_user_registrar_adapter(
    *,
    users: UsersContainer,
    credential_writer: CredentialWriterPort,
) -> SQLModelUserRegistrarAdapter:
    """Construct the users-feature ``UserRegistrarPort`` implementation.

    The registrar needs an authentication-side dependency (the credential
    writer) which is only available after the authentication container
    has been built; consumers therefore call this helper after both
    halves are wired and pass the result into the authorization
    container.
    """
    return SQLModelUserRegistrarAdapter(
        users=users.user_repository,
        credential_writer=credential_writer,
    )
