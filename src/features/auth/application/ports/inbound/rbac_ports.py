"""RBAC inbound port protocols.

One Protocol per RBAC use case, grouped here for concision since each has
a single execute() method and minimal surface area.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.features.auth.application.errors import AuthError
from src.features.auth.domain.models import AuditEvent, Permission, Role, User
from src.platform.shared.principal import Principal
from src.platform.shared.result import Result


class ListRolesPort(Protocol):
    def execute(
        self, *, limit: int = 100, offset: int = 0
    ) -> Result[list[Role], AuthError]: ...


class ListUsersPort(Protocol):
    def execute(
        self, *, limit: int = 100, offset: int = 0
    ) -> Result[list[User], AuthError]: ...


class CreateRolePort(Protocol):
    def execute(
        self,
        *,
        actor: Principal | None,
        name: str,
        description: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[Role, AuthError]: ...


class UpdateRolePort(Protocol):
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
    ) -> Result[Role, AuthError]: ...


class ListPermissionsPort(Protocol):
    def execute(
        self, *, limit: int = 100, offset: int = 0
    ) -> Result[list[Permission], AuthError]: ...


class CreatePermissionPort(Protocol):
    def execute(
        self,
        *,
        actor: Principal | None,
        name: str,
        description: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[Permission, AuthError]: ...


class AssignRolePermissionPort(Protocol):
    def execute(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        permission_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]: ...


class RemoveRolePermissionPort(Protocol):
    def execute(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        permission_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]: ...


class AssignUserRolePort(Protocol):
    def execute(
        self,
        *,
        actor: Principal,
        user_id: UUID,
        role_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]: ...


class RemoveUserRolePort(Protocol):
    def execute(
        self,
        *,
        actor: Principal,
        user_id: UUID,
        role_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[None, AuthError]: ...


class SeedInitialDataPort(Protocol):
    def execute(self) -> Result[None, AuthError]: ...


class BootstrapSuperAdminPort(Protocol):
    def execute(
        self,
        *,
        email: str,
        password: str,
    ) -> Result[User, AuthError]: ...


class ListAuditEventsPort(Protocol):
    def execute(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> Result[list[AuditEvent], AuthError]: ...
