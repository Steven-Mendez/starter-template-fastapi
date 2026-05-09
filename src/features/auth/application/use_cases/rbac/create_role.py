from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.errors import AuthError, ConflictError
from src.features.auth.application.normalization import (
    is_role_name,
    normalize_role_name,
)
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.domain.models import Role
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class CreateRole:
    _repository: AuthRepositoryPort

    def execute(
        self,
        *,
        actor: Principal | None,
        name: str,
        description: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[Role, AuthError]:
        normalized = normalize_role_name(name)
        if not is_role_name(normalized):
            return Err(ConflictError("Invalid role name"))
        role = self._repository.create_role(name=normalized, description=description)
        if role is None:
            return Err(ConflictError("Role already exists"))
        metadata: dict = {"role_id": str(role.id), "role_name": role.name}
        if actor is not None:
            metadata["actor"] = {
                "user_id": str(actor.user_id),
                "roles": sorted(actor.roles),
                "permissions": sorted(actor.permissions),
            }
        self._repository.record_audit_event(
            event_type="rbac.role_created",
            user_id=actor.user_id if actor is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
        return Ok(role)
