"""Administrative HTTP routes guarded by the system-admin relationship.

Each endpoint is gated by ``require_authorization`` against the
``system:main`` resource; only users that hold the ``admin`` relation
on the system singleton can call them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from src.features.authentication.adapters.inbound.http.errors import (
    raise_http_from_auth_error,
)
from src.features.authentication.adapters.inbound.http.schemas import (
    AuditEventRead,
    AuditLogRead,
    UserPublic,
)
from src.features.authentication.composition.app_state import get_auth_container
from src.platform.api.authorization import require_authorization
from src.platform.shared.result import Err, Ok

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get(
    "/users",
    response_model=list[UserPublic],
    dependencies=[require_authorization("manage_users", "system", None)],
)
def list_users(
    request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[UserPublic]:
    """Return user accounts ordered by email, paginated at the database level."""
    result = get_auth_container(request).list_users.execute(limit=limit, offset=offset)
    match result:
        case Ok(value=users):
            return [UserPublic.model_validate(u) for u in users]
        case Err(error=exc):
            raise_http_from_auth_error(exc)


@admin_router.get(
    "/audit-log",
    response_model=AuditLogRead,
    dependencies=[require_authorization("read_audit", "system", None)],
)
def list_audit_log(
    request: Request,
    user_id: Annotated[UUID | None, Query()] = None,
    event_type: Annotated[str | None, Query(min_length=1, max_length=150)] = None,
    since: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AuditLogRead:
    """Return filtered auth/authz audit events for system-admin inspection."""
    result = get_auth_container(request).list_audit_events.execute(
        user_id=user_id,
        event_type=event_type,
        since=since,
        limit=limit,
    )
    match result:
        case Ok(value=events):
            items = [AuditEventRead.model_validate(event) for event in events]
            return AuditLogRead(items=items, count=len(items), limit=limit)
        case Err(error=exc):
            raise_http_from_auth_error(exc)
