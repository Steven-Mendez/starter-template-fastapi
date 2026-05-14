"""Routes for the authenticated user's own profile.

``GET /me`` returns the calling user's record; ``PATCH /me`` updates
mutable profile fields; ``DELETE /me`` deactivates the account.
Authentication is enforced by the platform principal resolver via the
``CurrentPrincipal`` dependency.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app_platform.api.authorization import CurrentPrincipalDep
from app_platform.shared.result import Err, Ok
from features.authentication.adapters.inbound.http import clear_refresh_cookie
from features.users.adapters.inbound.http.schemas import (
    UpdateProfileRequest,
    UserPublic,
)
from features.users.application.errors import (
    UserAlreadyExistsError,
    UserNotFoundError,
)
from features.users.composition.app_state import get_users_container

me_router = APIRouter(tags=["me"])


@me_router.get("/me", response_model=UserPublic)
def get_me(request: Request, principal: CurrentPrincipalDep) -> UserPublic:
    """Return the calling user's profile."""
    container = get_users_container(request)
    result = container.get_user_by_id.execute(principal.user_id)
    match result:
        case Ok(value=user):
            return UserPublic.model_validate(user)
        case Err(error=err):
            if isinstance(err, UserNotFoundError):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
            )


@me_router.patch("/me", response_model=UserPublic)
def update_me(
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
            if isinstance(err, UserAlreadyExistsError):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Email already in use"
                )
            if isinstance(err, UserNotFoundError):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
            )


@me_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
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
            if isinstance(err, UserNotFoundError):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
            )
