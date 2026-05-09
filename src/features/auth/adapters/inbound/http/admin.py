"""Administrative HTTP routes for managing roles, permissions, and assignments.

Every endpoint is gated by an RBAC dependency declared in the route
decorator (``require_permissions`` / ``require_any_permission``) and any
mutation is delegated to :class:`RBACService`, which records audit events
and bumps ``authz_version`` so already-issued tokens reflect the change
on their next request.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from src.features.auth.adapters.inbound.http.auth import _client_ip, _user_agent
from src.features.auth.adapters.inbound.http.dependencies import (
    CurrentPrincipalDep,
    require_any_permission,
    require_permissions,
)
from src.features.auth.adapters.inbound.http.errors import raise_http_from_auth_error
from src.features.auth.adapters.inbound.http.schemas import (
    AuditEventRead,
    AuditLogRead,
    MessageResponse,
    PermissionAssignmentRequest,
    PermissionCreate,
    PermissionRead,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserPublic,
    UserRoleAssignmentRequest,
)
from src.features.auth.application.errors import AuthError
from src.features.auth.composition.app_state import get_auth_container

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get(
    "/users",
    response_model=list[UserPublic],
    dependencies=[require_any_permission("users:read", "users:roles:manage")],
)
def list_users(
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[UserPublic]:
    """Return user accounts ordered by email, paginated at the database level."""
    users = get_auth_container(request).rbac_service.list_users(
        limit=limit, offset=offset
    )
    return [UserPublic.model_validate(u) for u in users]


@admin_router.get(
    "/audit-log",
    response_model=AuditLogRead,
    dependencies=[require_permissions("audit:read")],
)
def list_audit_log(
    request: Request,
    user_id: Annotated[UUID | None, Query()] = None,
    event_type: Annotated[str | None, Query(min_length=1, max_length=150)] = None,
    since: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AuditLogRead:
    """Return filtered auth/RBAC audit events for super-admin inspection."""
    events = get_auth_container(request).rbac_service.list_audit_events(
        user_id=user_id,
        event_type=event_type,
        since=since,
        limit=limit,
    )
    items = [AuditEventRead.model_validate(event) for event in events]
    return AuditLogRead(items=items, count=len(items), limit=limit)


@admin_router.get(
    "/roles",
    response_model=list[RoleRead],
    dependencies=[require_any_permission("roles:read", "roles:manage")],
)
def list_roles(
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[RoleRead]:
    """Return roles ordered by name, paginated at the database level."""
    roles = get_auth_container(request).rbac_service.list_roles(
        limit=limit, offset=offset
    )
    return [RoleRead.model_validate(r) for r in roles]


@admin_router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permissions("roles:manage")],
)
def create_role(
    body: RoleCreate,
    principal: CurrentPrincipalDep,
    request: Request,
) -> RoleRead:
    """Create a new role from a normalised name and optional description."""
    try:
        role = get_auth_container(request).rbac_service.create_role(
            actor=principal,
            name=body.name,
            description=body.description,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return RoleRead.model_validate(role)
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@admin_router.patch(
    "/roles/{role_id}",
    response_model=RoleRead,
    dependencies=[require_permissions("roles:manage")],
)
def patch_role(
    role_id: UUID,
    body: RoleUpdate,
    principal: CurrentPrincipalDep,
    request: Request,
) -> RoleRead:
    """Update mutable role fields.

    Toggling ``is_active`` revokes affected tokens immediately.
    """
    try:
        role = get_auth_container(request).rbac_service.update_role(
            actor=principal,
            role_id=role_id,
            name=body.name,
            description=body.description,
            is_active=body.is_active,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return RoleRead.model_validate(role)
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@admin_router.get(
    "/permissions",
    response_model=list[PermissionRead],
    dependencies=[require_any_permission("permissions:read", "permissions:manage")],
)
def list_permissions(
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[PermissionRead]:
    """Return permissions ordered by name, paginated at the database level."""
    permissions = get_auth_container(request).rbac_service.list_permissions(
        limit=limit, offset=offset
    )
    return [PermissionRead.model_validate(p) for p in permissions]


@admin_router.post(
    "/permissions",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permissions("permissions:manage")],
)
def create_permission(
    body: PermissionCreate,
    principal: CurrentPrincipalDep,
    request: Request,
) -> PermissionRead:
    """Create a new permission with a validated ``resource:action`` name."""
    try:
        permission = get_auth_container(request).rbac_service.create_permission(
            actor=principal,
            name=body.name,
            description=body.description,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return PermissionRead.model_validate(permission)
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@admin_router.post(
    "/roles/{role_id}/permissions",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permissions("permissions:manage")],
)
def add_role_permission(
    role_id: UUID,
    body: PermissionAssignmentRequest,
    principal: CurrentPrincipalDep,
    request: Request,
) -> MessageResponse:
    """Grant a permission to a role and invalidate tokens of all role holders."""
    try:
        get_auth_container(request).rbac_service.assign_role_permission(
            actor=principal,
            role_id=role_id,
            permission_id=body.permission_id,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return MessageResponse(message="Permission assigned")
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@admin_router.delete(
    "/roles/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_permissions("permissions:manage")],
)
def remove_role_permission(
    role_id: UUID,
    permission_id: UUID,
    principal: CurrentPrincipalDep,
    request: Request,
) -> Response:
    """Revoke a permission from a role and invalidate tokens of all role holders."""
    try:
        get_auth_container(request).rbac_service.remove_role_permission(
            actor=principal,
            role_id=role_id,
            permission_id=permission_id,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@admin_router.post(
    "/users/{user_id}/roles",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permissions("users:roles:manage")],
)
def add_user_role(
    user_id: UUID,
    body: UserRoleAssignmentRequest,
    principal: CurrentPrincipalDep,
    request: Request,
) -> MessageResponse:
    """Assign a role to a user. The user's authz_version is bumped automatically."""
    try:
        get_auth_container(request).rbac_service.assign_user_role(
            actor=principal,
            user_id=user_id,
            role_id=body.role_id,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return MessageResponse(message="Role assigned")
    except AuthError as exc:
        raise_http_from_auth_error(exc)


@admin_router.delete(
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_permissions("users:roles:manage")],
)
def remove_user_role(
    user_id: UUID,
    role_id: UUID,
    principal: CurrentPrincipalDep,
    request: Request,
) -> Response:
    """Revoke a role from a user."""
    try:
        get_auth_container(request).rbac_service.remove_user_role(
            actor=principal,
            user_id=user_id,
            role_id=role_id,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AuthError as exc:
        raise_http_from_auth_error(exc)
