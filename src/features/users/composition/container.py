"""Composition root for the users feature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.engine import Engine

from features.file_storage.application.ports.file_storage_port import FileStoragePort
from features.outbox.application.ports.outbox_uow_port import OutboxUnitOfWorkPort
from features.users.adapters.outbound.authz_version import (
    SQLModelUserAuthzVersionAdapter,
)
from features.users.adapters.outbound.file_storage_user_assets import (
    FileStorageUserAssetsAdapter,
)
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from features.users.adapters.outbound.user_registrar import (
    SQLModelUserRegistrarAdapter,
)
from features.users.application.ports.credential_writer_port import (
    CredentialWriterPort,
)
from features.users.application.ports.user_assets_cleanup_port import (
    UserAssetsCleanupPort,
)
from features.users.application.use_cases.deactivate_user import DeactivateUser
from features.users.application.use_cases.get_user_by_email import (
    GetUserByEmail,
)
from features.users.application.use_cases.get_user_by_id import GetUserById
from features.users.application.use_cases.list_users import ListUsers
from features.users.application.use_cases.register_user import RegisterUser
from features.users.application.use_cases.update_profile import UpdateProfile


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

    def shutdown(self) -> None:
        # The engine is shared with the authentication container; it is
        # disposed there. Nothing per-feature to release.
        return None

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
