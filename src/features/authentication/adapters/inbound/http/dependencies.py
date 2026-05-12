"""FastAPI dependencies that resolve the current principal.

The auth feature exposes only principal-resolution helpers here. All
authorization gating uses the platform-level ``require_authorization``
dependency, which calls the AuthorizationPort registered on app.state.
"""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.features.authentication.adapters.inbound.http.errors import (
    raise_http_from_auth_error,
)
from src.features.authentication.composition.app_state import get_auth_container
from src.platform.api.request_state import set_actor_id
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok

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


def _forbidden(detail: str = "Permission denied") -> HTTPException:
    """Build a 403 response with a customisable detail message."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def get_current_principal(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)] = None,
) -> Principal:
    """Resolve the authenticated principal from the Bearer token."""
    if creds is None:
        raise _credentials_exception()
    token = creds.credentials
    container = get_auth_container(request)
    result = container.resolve_principal.execute(token)
    match result:
        case Ok(value=principal):
            # Publish the actor id onto request.state so other features can
            # stamp audit columns without importing from auth.
            set_actor_id(request, principal.user_id)
            return principal
        case Err(error=exc):
            raise_http_from_auth_error(exc)


def get_current_user(principal: "CurrentPrincipalDep") -> Principal:
    """Alias for :func:`get_current_principal` kept for naming convenience."""
    return principal


def require_active_user(principal: "CurrentPrincipalDep") -> Principal:
    """Resolve the principal and additionally require an active account."""
    if not principal.is_active:
        raise _forbidden("Inactive user")
    return principal


CurrentPrincipalDep: TypeAlias = Annotated[Principal, Depends(get_current_principal)]
CurrentUserDep: TypeAlias = Annotated[Principal, Depends(get_current_user)]
ActiveUserDep: TypeAlias = Annotated[Principal, Depends(require_active_user)]
