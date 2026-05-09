from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.errors import AuthError
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.seed import (
    ALL_PERMISSIONS,
    ROLE_DESCRIPTIONS,
    ROLE_PERMISSIONS,
)
from src.features.auth.domain.models import Permission, Role
from src.platform.shared.result import Ok, Result


@dataclass(slots=True)
class SeedInitialData:
    """Ensure the default permissions, roles, and role-permission mappings exist."""

    _repository: AuthRepositoryPort

    def execute(self) -> Result[None, AuthError]:
        permissions: dict[str, Permission] = {}
        for name, description in ALL_PERMISSIONS.items():
            permission = self._repository.get_permission_by_name(name)
            if permission is None:
                permission = self._repository.create_permission(
                    name=name, description=description
                )
            if permission is not None:
                permissions[name] = permission

        roles: dict[str, Role] = {}
        for role_name, description in ROLE_DESCRIPTIONS.items():
            role = self._repository.get_role_by_name(role_name)
            if role is None:
                role = self._repository.create_role(
                    name=role_name, description=description
                )
            if role is not None:
                roles[role_name] = role

        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role = roles.get(role_name)
            if role is None:
                continue
            for permission_name in permission_names:
                permission = permissions.get(permission_name)
                if permission is not None:
                    self._repository.assign_role_permission(role.id, permission.id)

        return Ok(None)
