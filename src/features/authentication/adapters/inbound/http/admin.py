"""Administrative HTTP routes guarded by the system-admin relationship.

Each endpoint is gated by ``require_authorization`` against the
``system:main`` resource; only users that hold the ``admin`` relation
on the system singleton can call them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from app_platform.api.authorization import require_authorization
from app_platform.shared.result import Err, Ok
from features.authentication.adapters.inbound.http.cursor import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from features.authentication.adapters.inbound.http.errors import (
    raise_http_from_auth_error,
)
from features.authentication.adapters.inbound.http.schemas import (
    AuditEventRead,
    AuditLogRead,
)
from features.authentication.composition.app_state import get_auth_container

admin_router = APIRouter(prefix="/admin", tags=["admin"])


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
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AuditLogRead:
    """Return filtered auth/authz audit events, newest first, paginated.

    Pass the previous response's ``next_before`` back as ``?before=...``
    to walk further back in time. Malformed cursors are rejected with
    ``400 Bad Request`` and no database query runs.
    """
    decoded_before: tuple[datetime, UUID] | None = None
    if before is not None:
        try:
            decoded_before = decode_cursor(before)
        except InvalidCursorError as cursor_exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(cursor_exc),
            ) from cursor_exc

    result = get_auth_container(request).list_audit_events.execute(
        user_id=user_id,
        event_type=event_type,
        since=since,
        before=decoded_before,
        limit=limit,
    )
    match result:
        case Ok(value=events):
            items = [AuditEventRead.model_validate(event) for event in events]
            next_before: str | None = None
            # A full page implies more rows may exist. The next cursor
            # is the tail row's ``(created_at, id)`` — i.e. the smallest
            # timestamp on this page — so paging continues backwards.
            if len(items) == limit and events:
                tail = events[-1]
                next_before = encode_cursor(tail.created_at, tail.id)
            return AuditLogRead(
                items=items,
                count=len(items),
                limit=limit,
                next_before=next_before,
            )
        case Err(error=exc):
            raise_http_from_auth_error(exc)
    return None
