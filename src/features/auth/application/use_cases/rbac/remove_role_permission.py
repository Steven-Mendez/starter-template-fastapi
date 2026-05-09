from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features.auth.application.cache import PrincipalCachePort
from src.features.auth.application.errors import AuthError, NotFoundError
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class RemoveRolePermission:
    _repository: AuthRepositoryPort
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        permission_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]:
        if not self._repository.remove_role_permission(role_id, permission_id):
            return Err(NotFoundError("Role permission assignment not found"))
        self._repository.increment_authz_for_role_users(role_id)
        if self._cache is not None:
            for user_id in self._repository.list_user_ids_for_role(role_id):
                self._cache.invalidate_user(user_id)
        self._repository.record_audit_event(
            event_type="rbac.role_permission_removed",
            user_id=actor.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "role_id": str(role_id),
                "permission_id": str(permission_id),
                "actor": {
                    "user_id": str(actor.user_id),
                    "roles": sorted(actor.roles),
                    "permissions": sorted(actor.permissions),
                },
            },
        )
        return Ok(None)
