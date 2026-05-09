from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features.auth.application.cache import PrincipalCachePort
from src.features.auth.application.errors import AuthError, ConflictError, NotFoundError
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
class UpdateRole:
    _repository: AuthRepositoryPort
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        name: str | None,
        description: str | None,
        is_active: bool | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[Role, AuthError]:
        existing = self._repository.get_role(role_id)
        if existing is None:
            return Err(NotFoundError("Role not found"))
        normalized_name = normalize_role_name(name) if name is not None else None
        if normalized_name is not None and not is_role_name(normalized_name):
            return Err(ConflictError("Invalid role name"))
        updated = self._repository.update_role(
            role_id,
            name=normalized_name,
            description=description,
            is_active=is_active,
        )
        if updated is None:
            return Err(ConflictError("Role update failed"))
        if is_active is not None and is_active != existing.is_active:
            self._repository.increment_authz_for_role_users(role_id)
            if self._cache is not None:
                for user_id in self._repository.list_user_ids_for_role(role_id):
                    self._cache.invalidate_user(user_id)
        metadata = {
            "role_id": str(role_id),
            "actor": {
                "user_id": str(actor.user_id),
                "roles": sorted(actor.roles),
                "permissions": sorted(actor.permissions),
            },
        }
        self._repository.record_audit_event(
            event_type="rbac.role_updated",
            user_id=actor.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
        return Ok(updated)
