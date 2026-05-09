"""Role-based access control: roles, permissions, and their assignments.

Every mutation that changes who can do what bumps the affected users'
``authz_version`` so stale access tokens are rejected on their next request.
All operations are recorded in the audit log.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from src.features.auth.application.auth_service import AuthService

from src.features.auth.application.cache import PrincipalCachePort
from src.features.auth.application.errors import (
    ConflictError,
    DuplicateEmailError,
    NotFoundError,
)
from src.features.auth.application.normalization import (
    is_permission_name,
    is_role_name,
    normalize_email,
    normalize_permission_name,
    normalize_role_name,
)
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.seed import (
    ALL_PERMISSIONS,
    ROLE_DESCRIPTIONS,
    ROLE_PERMISSIONS,
)
from src.features.auth.application.types import Principal
from src.features.auth.domain.models import AuditEvent, Permission, Role, User

_logger = logging.getLogger(__name__)


class RBACService:
    """Manages roles, permissions, and their assignments.

    Every mutation that changes who can do what also bumps the affected users'
    ``authz_version`` so stale access tokens are rejected on the next request.
    All operations are recorded in the audit log.
    """

    def __init__(
        self,
        *,
        repository: AuthRepositoryPort,
        cache: PrincipalCachePort | None = None,
    ) -> None:
        self._repo = repository
        self._cache = cache

    def list_roles(self, *, limit: int = 100, offset: int = 0) -> list[Role]:
        """Return roles ordered alphabetically with DB-level pagination."""
        return self._repo.list_roles(limit=limit, offset=offset)

    def list_users(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        """Return users ordered by email with DB-level pagination."""
        return self._repo.list_users(limit=limit, offset=offset)

    def create_role(
        self,
        *,
        actor: Principal | None,
        name: str,
        description: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Role:
        """Create a new role with a normalised name.

        Args:
            actor: Principal performing the action; ``None`` during seeding.
            name: Role name; normalised to lowercase with underscores.
            description: Optional human-readable description.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.

        Returns:
            The newly created ``RoleTable`` row.

        Raises:
            ConflictError: If the name is invalid or already exists.
        """
        normalized = normalize_role_name(name)
        if not is_role_name(normalized):
            raise ConflictError("Invalid role name")
        role = self._repo.create_role(name=normalized, description=description)
        if role is None:
            raise ConflictError("Role already exists")
        self._audit(
            "rbac.role_created",
            actor,
            ip_address,
            user_agent,
            {"role_id": str(role.id), "role_name": role.name},
        )
        return role

    def update_role(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        name: str | None,
        description: str | None,
        is_active: bool | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Role:
        """Update mutable fields of a role.

        When ``is_active`` changes, all users holding the role have their
        ``authz_version`` bumped so the change takes effect immediately on
        their next request, without waiting for their tokens to expire.

        Args:
            actor: Principal performing the action.
            role_id: UUID of the role to update.
            name: New name, or ``None`` to leave unchanged.
            description: New description, or ``None`` to leave unchanged.
            is_active: New active flag, or ``None`` to leave unchanged.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.

        Returns:
            The updated ``RoleTable`` row.

        Raises:
            NotFoundError: If the role does not exist.
            ConflictError: If the new name is invalid or already taken.
        """
        existing = self._repo.get_role(role_id)
        if existing is None:
            raise NotFoundError("Role not found")
        normalized_name = normalize_role_name(name) if name is not None else None
        if normalized_name is not None and not is_role_name(normalized_name):
            raise ConflictError("Invalid role name")
        updated = self._repo.update_role(
            role_id,
            name=normalized_name,
            description=description,
            is_active=is_active,
        )
        if updated is None:
            raise ConflictError("Role update failed")
        if is_active is not None and is_active != existing.is_active:
            # Bump authz_version for all holders of this role so their next
            # request fails the version check and they must re-authenticate,
            # making role activation/deactivation take effect immediately.
            self._repo.increment_authz_for_role_users(role_id)
            self._invalidate_role_users(role_id)
        self._audit(
            "rbac.role_updated",
            actor,
            ip_address,
            user_agent,
            {"role_id": str(role_id)},
        )
        return updated

    def list_permissions(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[Permission]:
        """Return permissions ordered alphabetically with DB-level pagination."""
        return self._repo.list_permissions(limit=limit, offset=offset)

    def create_permission(
        self,
        *,
        actor: Principal | None,
        name: str,
        description: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Permission:
        """Create a new permission with a validated ``resource:action`` name.

        Args:
            actor: Principal performing the action; ``None`` during seeding.
            name: Permission name in ``resource:action`` format (e.g. ``"roles:read"``).
            description: Optional human-readable description.
            ip_address: Client IP for audit logging.
            user_agent: Client User-Agent for audit logging.

        Returns:
            The newly created ``PermissionTable`` row.

        Raises:
            ConflictError: If the name is invalid or already exists.
        """
        normalized = normalize_permission_name(name)
        if not is_permission_name(normalized):
            raise ConflictError("Invalid permission name")
        permission = self._repo.create_permission(
            name=normalized, description=description
        )
        if permission is None:
            raise ConflictError("Permission already exists")
        self._audit(
            "rbac.permission_created",
            actor,
            ip_address,
            user_agent,
            {"permission_id": str(permission.id), "permission_name": permission.name},
        )
        return permission

    def assign_role_permission(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        permission_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Grant a permission to a role and invalidate all affected tokens.

        All users holding the role have their ``authz_version`` bumped so the
        new permission is reflected immediately on their next request.

        Raises:
            NotFoundError: If the role or permission does not exist.
        """
        if not self._repo.assign_role_permission(role_id, permission_id):
            raise NotFoundError("Role or permission not found")
        # Invalidate existing tokens for all role members so the new permission
        # is not silently absent from in-flight access tokens.
        self._repo.increment_authz_for_role_users(role_id)
        self._invalidate_role_users(role_id)
        self._audit(
            "rbac.role_permission_added",
            actor,
            ip_address,
            user_agent,
            {"role_id": str(role_id), "permission_id": str(permission_id)},
        )

    def remove_role_permission(
        self,
        *,
        actor: Principal,
        role_id: UUID,
        permission_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Revoke a permission from a role and invalidate all affected tokens.

        All users holding the role have their ``authz_version`` bumped so they
        can no longer exercise the revoked permission after their next request,
        without waiting for their access tokens to expire.

        Raises:
            NotFoundError: If the role-permission assignment does not exist.
        """
        if not self._repo.remove_role_permission(role_id, permission_id):
            raise NotFoundError("Role permission assignment not found")
        # Invalidate tokens immediately so users cannot keep exercising a
        # permission that was just revoked for the duration of the token TTL.
        self._repo.increment_authz_for_role_users(role_id)
        self._invalidate_role_users(role_id)
        self._audit(
            "rbac.role_permission_removed",
            actor,
            ip_address,
            user_agent,
            {"role_id": str(role_id), "permission_id": str(permission_id)},
        )

    def assign_user_role(
        self,
        *,
        actor: Principal,
        user_id: UUID,
        role_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Grant a role to a user.

        The repository bumps the user's ``authz_version`` so the change
        takes effect on their next request.

        Raises:
            NotFoundError: If the user or role does not exist.
        """
        if not self._repo.assign_user_role(user_id, role_id):
            raise NotFoundError("User or role not found")
        self._invalidate_user(user_id)
        self._audit(
            "rbac.user_role_added",
            actor,
            ip_address,
            user_agent,
            {"target_user_id": str(user_id), "role_id": str(role_id)},
        )

    def remove_user_role(
        self,
        *,
        actor: Principal,
        user_id: UUID,
        role_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Revoke a role from a user.

        Raises:
            NotFoundError: If the user-role assignment does not exist.
        """
        if not self._repo.remove_user_role(user_id, role_id):
            raise NotFoundError("User role assignment not found")
        self._invalidate_user(user_id)
        self._audit(
            "rbac.user_role_removed",
            actor,
            ip_address,
            user_agent,
            {"target_user_id": str(user_id), "role_id": str(role_id)},
        )

    def seed_initial_data(self) -> None:
        """Ensure the default permissions, roles, and role-permission mappings exist.

        Idempotent: skips any item that already exists. Safe to run on every
        deployment or startup without duplicating data.
        """
        permissions: dict[str, Permission] = {}
        for name, description in ALL_PERMISSIONS.items():
            permission = self._repo.get_permission_by_name(name)
            if permission is None:
                permission = self._repo.create_permission(
                    name=name, description=description
                )
            if permission is not None:
                permissions[name] = permission
        roles: dict[str, Role] = {}
        for role_name, description in ROLE_DESCRIPTIONS.items():
            role = self._repo.get_role_by_name(role_name)
            if role is None:
                role = self._repo.create_role(name=role_name, description=description)
            if role is not None:
                roles[role_name] = role
        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role = roles.get(role_name)
            if role is None:
                continue
            for permission_name in permission_names:
                permission = permissions.get(permission_name)
                if permission is not None:
                    self._repo.assign_role_permission(role.id, permission.id)

    def bootstrap_super_admin(
        self,
        *,
        auth_service: "AuthService",
        email: str,
        password: str,
    ) -> User:
        """Seed data and ensure the given account has the ``super_admin`` role.

        Creates the account if it does not exist yet. Intended for one-time
        bootstrap via the management CLI, not the public API, so it bypasses
        the rate limiter and audit trail of a normal registration.

        Args:
            auth_service: Used to register the account if it does not exist.
            email: Email of the super admin account to create or promote.
            password: Plaintext password (only used when creating a new account).

        Returns:
            The ``UserTable`` row with the ``super_admin`` role assigned.

        Raises:
            NotFoundError: If the ``super_admin`` role was not seeded.
        """
        self.seed_initial_data()
        normalized_email = normalize_email(email)
        user = self._repo.get_user_by_email(normalized_email)
        if user is None:
            try:
                user = auth_service.register(email=normalized_email, password=password)
            except DuplicateEmailError:
                # Two replicas racing at startup can both reach this branch.
                # The unique email constraint ensures only one INSERT succeeds;
                # the loser retries the lookup to find the row the winner wrote.
                user = self._repo.get_user_by_email(normalized_email)
                if user is None:
                    raise
        role = self._repo.get_role_by_name("super_admin")
        if role is None:
            raise NotFoundError("super_admin role not found")
        self._repo.assign_user_role(user.id, role.id)
        self._invalidate_user(user.id)
        self._repo.record_audit_event(
            event_type="rbac.super_admin_bootstrapped",
            user_id=user.id,
            metadata={"role_id": str(role.id)},
        )
        refreshed = self._repo.get_user_by_id(user.id)
        if refreshed is None:
            raise NotFoundError("User not found")
        return refreshed

    def list_audit_events(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Return filtered audit events for administrative inspection."""
        bounded_limit = max(1, min(limit, 500))
        return self._repo.list_audit_events(
            user_id=user_id,
            event_type=event_type,
            since=since,
            limit=bounded_limit,
        )

    def _invalidate_user(self, user_id: UUID) -> None:
        if self._cache is not None:
            self._cache.invalidate_user(user_id)

    def _invalidate_role_users(self, role_id: UUID) -> None:
        if self._cache is None:
            return
        for user_id in self._repo.list_user_ids_for_role(role_id):
            self._cache.invalidate_user(user_id)

    def _audit(
        self,
        event_type: str,
        actor: Principal | None,
        ip_address: str | None,
        user_agent: str | None,
        metadata: dict[str, Any],
    ) -> None:
        """Write an RBAC audit event, recording the acting principal if present.

        Embeds an ``actor`` snapshot (id, roles, permissions at the time of
        the action) so future audits can detect privilege escalation by
        comparing the actor's authority against the action they performed.
        """
        enriched = dict(metadata)
        if actor is not None:
            enriched["actor"] = {
                "user_id": str(actor.user_id),
                "roles": sorted(actor.roles),
                "permissions": sorted(actor.permissions),
            }
        self._repo.record_audit_event(
            event_type=event_type,
            user_id=actor.user_id if actor is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=enriched,
        )
