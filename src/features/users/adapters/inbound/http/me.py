"""Routes for the authenticated user's own profile.

``GET /me`` returns the calling user's record; ``PATCH /me`` updates
mutable profile fields; ``DELETE /me`` deactivates the account.
Authentication is enforced by the platform principal resolver via the
``CurrentPrincipal`` dependency.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from src.features.users.adapters.inbound.http.schemas import (
    UpdateProfileRequest,
    UserPublic,
)
from src.features.users.application.errors import UserError
from src.features.users.composition.app_state import get_users_container
from src.platform.api.authorization import CurrentPrincipalDep
from src.platform.shared.result import Err, Ok

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
            if err is UserError.NOT_FOUND:
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
            if err is UserError.DUPLICATE_EMAIL:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Email already in use"
                )
            if err is UserError.NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
            )


@me_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(request: Request, principal: CurrentPrincipalDep) -> None:
    """Deactivate the calling user (soft delete)."""
    container = get_users_container(request)
    result = container.deactivate_user.execute(principal.user_id)
    match result:
        case Ok():
            return None
        case Err(error=err):
            if err is UserError.NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
            )
