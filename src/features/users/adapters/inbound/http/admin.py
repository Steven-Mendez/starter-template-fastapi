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
from features.users.adapters.inbound.http.schemas import UserPublic
from features.users.composition.app_state import get_users_container

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
    """Return user accounts ordered by ``created_at``, paginated."""
    result = get_users_container(request).list_users.execute(limit=limit, offset=offset)
    match result:
        case Ok(value=users):
            return [UserPublic.model_validate(u) for u in users]
        case Err(error=err):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
            )
