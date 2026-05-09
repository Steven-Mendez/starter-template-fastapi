"""FastAPI dependencies that resolve the current principal and enforce RBAC.

The exported ``CurrentPrincipalDep`` / ``ActiveUserDep`` aliases keep route
signatures short, while ``require_roles`` / ``require_permissions`` /
``require_any_permission`` produce ``Depends`` objects suitable for use in
either function parameters or ``dependencies=[...]`` lists.
"""

from __future__ import annotations

from typing import Annotated, Any, TypeAlias

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.features.auth.adapters.inbound.http.errors import raise_http_from_auth_error
from src.features.auth.application.errors import (
    AuthError,
    PermissionDeniedError,
)
from src.features.auth.application.services import ensure_permissions, ensure_roles
from src.features.auth.application.types import Principal
from src.features.auth.composition.app_state import get_auth_container

# HTTPBearer (not OAuth2 password) so Swagger UI "Authorize" accepts a pasted
# JWT: OAuth2PasswordBearer would POST form username/password to /auth/login,
# but login expects JSON { "email", "password" }.
_http_bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description=(
        "Paste the access_token from POST /auth/login "
        "(request body: JSON email + password)."
    ),
)


def _credentials_exception() -> HTTPException:
    """Build the canonical 401 response for missing or invalid credentials."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "Not enough permissions") -> HTTPException:
    """Build a 403 response with a customisable detail message."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def get_current_principal(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)] = None,
) -> Principal:
    """Resolve the authenticated principal from the Bearer token.

    Delegates token validation and principal resolution to ``AuthService``.
    Resolved principals may be cached for up to 30 seconds, so emergency
    permission revocations are not guaranteed to take effect instantly.

    Args:
        request: The current FastAPI ``Request``, used to access the container.
        creds: JWT access token from the ``Authorization: Bearer`` header.

    Returns:
        The verified and active ``Principal`` for the current request.

    Raises:
        HTTPException 401: If the token is missing, invalid, expired, or stale.
        HTTPException 403: If the user account is inactive.
    """
    if creds is None:
        raise _credentials_exception()
    token = creds.credentials
    container = get_auth_container(request)
    try:
        principal = container.auth_service.principal_from_access_token(token)
    except AuthError as exc:
        raise_http_from_auth_error(exc)
    # Publish the actor id onto request.state so other features (e.g. kanban)
    # can stamp audit columns without importing from auth and crossing a
    # feature-isolation boundary.
    request.state.actor_id = principal.user_id
    return principal


def get_current_user(principal: "CurrentPrincipalDep") -> Principal:
    """Alias for :func:`get_current_principal` kept for naming convenience."""
    return principal


def require_active_user(principal: "CurrentPrincipalDep") -> Principal:
    """Resolve the principal and additionally require an active account.

    ``get_current_principal`` already rejects inactive users, but this guard
    is kept as an explicit dependency so handlers can express the intent
    in their signature.
    """
    if not principal.is_active:
        raise _forbidden("Inactive user")
    return principal


CurrentPrincipalDep: TypeAlias = Annotated[Principal, Depends(get_current_principal)]
CurrentUserDep: TypeAlias = Annotated[Principal, Depends(get_current_user)]
ActiveUserDep: TypeAlias = Annotated[Principal, Depends(require_active_user)]


def require_roles(*roles: str) -> Any:
    """Return a FastAPI dependency that enforces role membership.

    The request is allowed if the principal holds **at least one** of the
    specified roles. RBAC is bypassed entirely when ``auth_rbac_enabled=False``.

    Args:
        *roles: One or more role names; membership in any one is sufficient.

    Returns:
        A FastAPI ``Depends`` object suitable for use in route signatures or
        the ``dependencies`` list of a route decorator.
    """
    required = set(roles)

    def dependency(
        request: Request,
        principal: CurrentPrincipalDep,
    ) -> Principal:
        container = get_auth_container(request)
        # Bypassing RBAC when disabled lets the API run in open mode during
        # development without changing every endpoint's dependency list.
        if not container.settings.auth_rbac_enabled:
            return principal
        try:
            ensure_roles(principal, required)
            return principal
        except PermissionDeniedError as exc:
            raise _forbidden("Not enough roles") from exc

    return Depends(dependency)


def require_permissions(*permissions: str) -> Any:
    """Alias for :func:`require_all_permissions`, used as the default in routes."""
    return require_all_permissions(*permissions)


def require_all_permissions(*permissions: str) -> Any:
    """Return a FastAPI dependency that requires **all** listed permissions.

    Args:
        *permissions: Every permission the principal must hold.

    Returns:
        A FastAPI ``Depends`` object.
    """
    required = set(permissions)

    def dependency(
        request: Request,
        principal: CurrentPrincipalDep,
    ) -> Principal:
        container = get_auth_container(request)
        if not container.settings.auth_rbac_enabled:
            return principal
        try:
            ensure_permissions(principal, required, any_=False)
            return principal
        except PermissionDeniedError as exc:
            raise _forbidden() from exc

    return Depends(dependency)


def require_any_permission(*permissions: str) -> Any:
    """Return a FastAPI dependency requiring **at least one** listed permission.

    Args:
        *permissions: The permission set; holding any one is sufficient.

    Returns:
        A FastAPI ``Depends`` object.
    """
    required = set(permissions)

    def dependency(
        request: Request,
        principal: CurrentPrincipalDep,
    ) -> Principal:
        container = get_auth_container(request)
        if not container.settings.auth_rbac_enabled:
            return principal
        try:
            ensure_permissions(principal, required, any_=True)
            return principal
        except PermissionDeniedError as exc:
            raise _forbidden() from exc

    return Depends(dependency)
