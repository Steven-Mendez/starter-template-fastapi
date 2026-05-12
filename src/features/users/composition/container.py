"""Composition root for the users feature."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from src.features.users.adapters.outbound.authz_version import (
    SQLModelUserAuthzVersionAdapter,
)
from src.features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from src.features.users.adapters.outbound.user_registrar import (
    SQLModelUserRegistrarAdapter,
)
from src.features.users.application.ports.credential_writer_port import (
    CredentialWriterPort,
)
from src.features.users.application.use_cases.deactivate_user import DeactivateUser
from src.features.users.application.use_cases.get_user_by_email import (
    GetUserByEmail,
)
from src.features.users.application.use_cases.get_user_by_id import GetUserById
from src.features.users.application.use_cases.list_users import ListUsers
from src.features.users.application.use_cases.register_user import RegisterUser
from src.features.users.application.use_cases.update_profile import UpdateProfile


@dataclass(slots=True)
class UsersContainer:
    """Bundle of singletons for the users feature."""

    user_repository: SQLModelUserRepository
    user_authz_version_adapter: SQLModelUserAuthzVersionAdapter
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


def build_users_container(*, engine: Engine) -> UsersContainer:
    """Construct the users container sharing the auth engine."""
    repository = SQLModelUserRepository(engine=engine)
    authz_version_adapter = SQLModelUserAuthzVersionAdapter(engine)
    return UsersContainer(
        user_repository=repository,
        user_authz_version_adapter=authz_version_adapter,
        register_user=RegisterUser(_users=repository),
        get_user_by_id=GetUserById(_users=repository),
        get_user_by_email=GetUserByEmail(_users=repository),
        update_profile=UpdateProfile(_users=repository),
        deactivate_user=DeactivateUser(_users=repository),
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
