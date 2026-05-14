"""Administrative HTTP routes for the users feature.

Currently exposes ``GET /admin/users``. The route is gated by
``require_authorization`` against the ``system:main`` resource; only
principals holding the ``admin`` relation on the system singleton can
call it.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request, Response, status

from app_platform.api.authorization import require_authorization
from app_platform.api.error_handlers_app_exception import ApplicationHTTPException
from app_platform.api.operation_ids import feature_operation_id
from app_platform.api.problem_types import ProblemType
from app_platform.api.responses import ADMIN_RESPONSES
from app_platform.observability.tracing import propagator_inject_current
from app_platform.shared.result import Err, Ok
from features.users.adapters.inbound.http.cursor import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from features.users.adapters.inbound.http.errors import raise_http_from_user_error
from features.users.adapters.inbound.http.schemas import (
    ErasureAccepted,
    ExportResponse,
    UserListPage,
    UserPublic,
)
from features.users.composition.app_state import get_users_container

admin_router = APIRouter(
    prefix="/admin",
    tags=["users"],
    generate_unique_id_function=feature_operation_id,
)

_ERASE_ESTIMATED_COMPLETION_SECONDS = 60


@admin_router.get(
    "/users",
    response_model=UserListPage,
    dependencies=[require_authorization("manage_users", "system", None)],
    responses=ADMIN_RESPONSES,
)
def admin_list_users(
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
            raise ApplicationHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                code="invalid_cursor",
                type_uri=ProblemType.ABOUT_BLANK,
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
            raise_http_from_user_error(err)
    return None


@admin_router.post(
    "/users/{user_id}/erase",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ErasureAccepted,
    dependencies=[require_authorization("manage_users", "system", None)],
    responses=ADMIN_RESPONSES,
)
def admin_erase_user(
    request: Request,
    response: Response,
    user_id: UUID,
) -> ErasureAccepted:
    """Admin path for GDPR Art. 17 erasure.

    Same enqueue-and-return-202 contract as ``DELETE /me/erase``, but
    gated by ``manage_users`` on ``system:main`` (the same predicate
    that protects the admin user-listing route). No password re-auth
    is required — the admin's session is the audit trail, the
    ``user.erased`` event records the actor implicitly via the audit
    row's metadata.
    """
    container = get_users_container(request)
    if container.job_queue is None:
        raise ApplicationHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Erasure pipeline is not wired",
            code="erasure_pipeline_unwired",
            type_uri=ProblemType.ABOUT_BLANK,
        )
    job_id = str(uuid4())
    # Direct (non-outbox) enqueue: inject the W3C trace carrier so the
    # handler-side spans become children of this request's trace.
    trace_carrier = propagator_inject_current()
    erase_payload: dict[str, object] = {
        "user_id": str(user_id),
        "reason": "admin_request",
        "job_id": job_id,
    }
    if trace_carrier:
        erase_payload["__trace"] = trace_carrier
    container.job_queue.enqueue("erase_user", erase_payload)
    response.headers["Location"] = f"/admin/users/{user_id}/erase/status/{job_id}"
    return ErasureAccepted(
        status="accepted",
        job_id=job_id,
        estimated_completion_seconds=_ERASE_ESTIMATED_COMPLETION_SECONDS,
    )


@admin_router.get(
    "/users/{user_id}/export",
    response_model=ExportResponse,
    dependencies=[require_authorization("manage_users", "system", None)],
    responses=ADMIN_RESPONSES,
)
def admin_export_user(
    request: Request,
    user_id: UUID,
) -> ExportResponse:
    """Admin path for GDPR Art. 15 export. Same response shape as ``/me/export``."""
    container = get_users_container(request)
    if container.export_user_data is None:
        raise ApplicationHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Export pipeline is not wired",
            code="export_pipeline_unwired",
            type_uri=ProblemType.ABOUT_BLANK,
        )
    result = container.export_user_data.execute(user_id)
    match result:
        case Ok(value=contract):
            return ExportResponse(
                download_url=contract.download_url,
                expires_at=contract.expires_at,
            )
        case Err(error=err):
            raise_http_from_user_error(err)
    return None
