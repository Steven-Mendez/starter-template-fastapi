"""Routes for the authenticated user's own profile.

``GET /me`` returns the calling user's record; ``PATCH /me`` updates
mutable profile fields; ``DELETE /me`` deactivates the account.
Authentication is enforced by the platform principal resolver via the
``CurrentPrincipal`` dependency.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request, Response, status

from app_platform.api.authorization import CurrentPrincipalDep
from app_platform.api.error_handlers_app_exception import ApplicationHTTPException
from app_platform.api.operation_ids import feature_operation_id
from app_platform.api.problem_types import ProblemType
from app_platform.api.responses import USERS_RESPONSES
from app_platform.observability.tracing import propagator_inject_current
from app_platform.shared.result import Err, Ok
from features.authentication.adapters.inbound.http import clear_refresh_cookie
from features.users.adapters.inbound.http.errors import raise_http_from_user_error
from features.users.adapters.inbound.http.schemas import (
    EraseSelfRequest,
    ErasureAccepted,
    ExportResponse,
    UpdateProfileRequest,
    UserPublic,
)
from features.users.composition.app_state import get_users_container

me_router = APIRouter(
    tags=["users"],
    generate_unique_id_function=feature_operation_id,
)

# Upper bound (in seconds) we promise clients the erase job will finish
# within. The job itself is bounded by the worker's job timeout, but
# this number is what the response body advertises.
_ERASE_ESTIMATED_COMPLETION_SECONDS = 60


@me_router.get("/me", response_model=UserPublic, responses=USERS_RESPONSES)
def get_me(request: Request, principal: CurrentPrincipalDep) -> UserPublic:
    """Return the calling user's profile."""
    container = get_users_container(request)
    result = container.get_user_by_id.execute(principal.user_id)
    match result:
        case Ok(value=user):
            return UserPublic.model_validate(user)
        case Err(error=err):
            raise_http_from_user_error(err)
    return None


@me_router.patch("/me", response_model=UserPublic, responses=USERS_RESPONSES)
def patch_me(
    request: Request,
    body: UpdateProfileRequest,
    principal: CurrentPrincipalDep,
) -> UserPublic:
    """Update the caller's profile (currently only email)."""
    container = get_users_container(request)
    result = container.update_profile.execute(
        user_id=principal.user_id,
        email=str(body.email) if body.email is not None else None,
    )
    match result:
        case Ok(value=user):
            return UserPublic.model_validate(user)
        case Err(error=err):
            raise_http_from_user_error(err)
    return None


@me_router.delete(
    "/me", status_code=status.HTTP_204_NO_CONTENT, responses=USERS_RESPONSES
)
def delete_me(
    request: Request,
    response: Response,
    principal: CurrentPrincipalDep,
) -> None:
    """Deactivate the calling user (soft delete).

    Self-deactivation is destructive: in a single response cycle we
    revoke every server-side refresh-token family for the user (inside
    the same Unit of Work that flips ``is_active=False``, wired into
    :class:`DeactivateUser` at composition time) and clear the
    browser-side refresh cookie. A client proxy could strip
    ``Set-Cookie``; the inline server-side revocation is the durable
    defense.
    """
    container = get_users_container(request)
    result = container.deactivate_user.execute(principal.user_id)
    match result:
        case Ok():
            clear_refresh_cookie(response, request)
            return
        case Err(error=err):
            raise_http_from_user_error(err)


@me_router.delete(
    "/me/erase",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ErasureAccepted,
    responses=USERS_RESPONSES,
)
def erase_me(
    request: Request,
    response: Response,
    body: EraseSelfRequest,
    principal: CurrentPrincipalDep,
) -> ErasureAccepted:
    """GDPR Art. 17 self-erase.

    Re-auth on current password is required — a stolen access token
    alone cannot erase the account. Wrong password → 401. Success →
    202 Accepted with a job id; the actual scrub runs in the worker
    via the ``erase_user`` background job (see ``EraseUser`` use case).

    A user without a password credential (future SSO-only flows) is
    out of scope for this proposal; the password verifier returns
    ``False`` for that case, surfacing as 401, and a follow-up change
    can swap in a "fresh access-token issued < 5 min ago" check
    without altering the response shape.
    """
    container = get_users_container(request)
    if container.password_verifier is None or container.job_queue is None:
        # Defensive: production wiring always provides both. If we get
        # here in production something is mis-composed; better to 500
        # than to silently erase without re-auth.
        raise ApplicationHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Erasure pipeline is not wired",
            code="erasure_pipeline_unwired",
            type_uri=ProblemType.ABOUT_BLANK,
        )
    if not container.password_verifier(principal.user_id, body.password):
        raise ApplicationHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            code="invalid_credentials",
            type_uri=ProblemType.AUTH_INVALID_CREDENTIALS,
        )
    job_id = str(uuid4())
    # Direct (non-outbox) enqueue: inject the W3C trace carrier so the
    # handler-side spans become children of this request's trace.
    trace_carrier = propagator_inject_current()
    erase_payload: dict[str, object] = {
        "user_id": str(principal.user_id),
        "reason": "self_request",
        "job_id": job_id,
    }
    if trace_carrier:
        erase_payload["__trace"] = trace_carrier
    container.job_queue.enqueue("erase_user", erase_payload)
    response.headers["Location"] = f"/me/erase/status/{job_id}"
    return ErasureAccepted(
        status="accepted",
        job_id=job_id,
        estimated_completion_seconds=_ERASE_ESTIMATED_COMPLETION_SECONDS,
    )


@me_router.get("/me/export", response_model=ExportResponse, responses=USERS_RESPONSES)
def export_me(
    request: Request,
    principal: CurrentPrincipalDep,
) -> ExportResponse:
    """GDPR Art. 15 self-export.

    Returns a signed URL pointing at a JSON blob containing the user's
    row, profile fields, audit events, and file metadata. The blob is
    materialised synchronously; clients fetch it from the wired
    file-storage backend within ``expires_at``.
    """
    container = get_users_container(request)
    if container.export_user_data is None:
        raise ApplicationHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Export pipeline is not wired",
            code="export_pipeline_unwired",
            type_uri=ProblemType.ABOUT_BLANK,
        )
    result = container.export_user_data.execute(principal.user_id)
    match result:
        case Ok(value=contract):
            return ExportResponse(
                download_url=contract.download_url,
                expires_at=contract.expires_at,
            )
        case Err(error=err):
            raise_http_from_user_error(err)
    return None
