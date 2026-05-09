from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.errors import AuthError, ConflictError
from src.features.auth.application.normalization import (
    is_permission_name,
    normalize_permission_name,
)
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.domain.models import Permission
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class CreatePermission:
    _repository: AuthRepositoryPort

    def execute(
        self,
        *,
        actor: Principal | None,
        name: str,
        description: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[Permission, AuthError]:
        normalized = normalize_permission_name(name)
        if not is_permission_name(normalized):
            return Err(ConflictError("Invalid permission name"))
        permission = self._repository.create_permission(
            name=normalized, description=description
        )
        if permission is None:
            return Err(ConflictError("Permission already exists"))
        metadata: dict = {
            "permission_id": str(permission.id),
            "permission_name": permission.name,
        }
        if actor is not None:
            metadata["actor"] = {
                "user_id": str(actor.user_id),
                "roles": sorted(actor.roles),
                "permissions": sorted(actor.permissions),
            }
        self._repository.record_audit_event(
            event_type="rbac.permission_created",
            user_id=actor.user_id if actor is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
        return Ok(permission)
