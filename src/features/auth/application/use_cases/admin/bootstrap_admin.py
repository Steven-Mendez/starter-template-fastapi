"""Bootstrap the first system administrator under the ReBAC model.

Creates (or looks up) the user account identified by the configured
email and writes the single ``system:main#admin@user:{id}`` tuple. The
authorization port handles ``authz_version`` bumping.

Re-running is safe: an existing user is reused, and the tuple write is
idempotent thanks to the relationships table's unique constraint.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.authorization.ports import AuthorizationPort
from src.features.auth.application.authorization.types import Relationship
from src.features.auth.application.errors import (
    AuthError,
    DuplicateEmailError,
    NotFoundError,
)
from src.features.auth.application.normalization import normalize_email
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.use_cases.auth.register_user import RegisterUser
from src.features.auth.domain.models import User
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class BootstrapSystemAdmin:
    """Ensure the configured account exists and holds ``system:main#admin``."""

    _repository: AuthRepositoryPort
    _register_user: RegisterUser
    _authorization: AuthorizationPort

    def execute(self, *, email: str, password: str) -> Result[User, AuthError]:
        normalized_email = normalize_email(email)
        user = self._repository.get_user_by_email(normalized_email)
        if user is None:
            reg_result = self._register_user.execute(
                email=normalized_email, password=password
            )
            match reg_result:
                case Ok(value=created):
                    user = created
                case Err(error=exc):
                    if isinstance(exc, DuplicateEmailError):
                        # Two replicas raced at startup; retry the lookup.
                        user = self._repository.get_user_by_email(normalized_email)
                        if user is None:
                            return Err(exc)
                    else:
                        return Err(exc)

        self._authorization.write_relationships(
            [
                Relationship(
                    resource_type="system",
                    resource_id="main",
                    relation="admin",
                    subject_type="user",
                    subject_id=str(user.id),
                )
            ]
        )
        self._repository.record_audit_event(
            event_type="authz.bootstrap_admin_assigned",
            user_id=user.id,
        )
        refreshed = self._repository.get_user_by_id(user.id)
        if refreshed is None:
            return Err(NotFoundError("User not found"))
        return Ok(refreshed)
