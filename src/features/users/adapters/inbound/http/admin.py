"""Administrative HTTP routes for the users feature.

Currently exposes ``GET /admin/users``. The route is gated by
``require_authorization`` against the ``system:main`` resource; only
principals holding the ``admin`` relation on the system singleton can
call it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app_platform.api.authorization import require_authorization
from app_platform.shared.result import Err, Ok
from features.users.adapters.inbound.http.cursor import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from features.users.adapters.inbound.http.schemas import (
    UserListPage,
    UserPublic,
)
from features.users.composition.app_state import get_users_container

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get(
    "/users",
    response_model=UserListPage,
    dependencies=[require_authorization("manage_users", "system", None)],
)
def list_users(
    request: Request,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> UserListPage:
    """Return a keyset-paginated page of users.

    Pass the previous response's ``next_cursor`` back as ``?cursor=...``
    to fetch the next page. A missing ``next_cursor`` field in the
    response means no more rows are available. Malformed cursors are
    rejected with ``400 Bad Request`` and no database query runs.
    """
    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    result = get_users_container(request).list_users.execute(
        cursor=decoded_cursor, limit=limit
    )
    match result:
        case Ok(value=users):
            items = [UserPublic.model_validate(u) for u in users]
            next_cursor: str | None = None
            # A full page means another page may exist; emit a cursor so
            # the caller can paginate forward. A partial page is the last
            # page by definition — no cursor.
            if len(items) == limit and items:
                last = users[-1]
                next_cursor = encode_cursor(last.created_at, last.id)
            return UserListPage(
                items=items,
                count=len(items),
                limit=limit,
                next_cursor=next_cursor,
            )
        case Err(error=err):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
            )
