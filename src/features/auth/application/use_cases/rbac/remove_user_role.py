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
class RemoveUserRole:
    _repository: AuthRepositoryPort
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        *,
        actor: Principal,
        user_id: UUID,
        role_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]:
        if not self._repository.remove_user_role(user_id, role_id):
            return Err(NotFoundError("User role assignment not found"))
        if self._cache is not None:
            self._cache.invalidate_user(user_id)
        self._repository.record_audit_event(
            event_type="rbac.user_role_removed",
            user_id=actor.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "target_user_id": str(user_id),
                "role_id": str(role_id),
                "actor": {
                    "user_id": str(actor.user_id),
                    "roles": sorted(actor.roles),
                    "permissions": sorted(actor.permissions),
                },
            },
        )
        return Ok(None)
