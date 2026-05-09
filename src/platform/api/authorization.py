"""FastAPI-bound authorization dependencies for the platform layer.

``get_current_principal`` reads the resolver from
``request.app.state.principal_resolver`` so the platform never imports a
feature module.  ``main.py`` registers the real resolver during lifespan;
e2e test fixtures register a fake one.

``require_permissions``, ``require_any_permission``, and ``require_roles``
each return a ``Depends`` object and chain off ``get_current_principal`` so a
single bearer token lookup satisfies the entire guard chain.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, TypeAlias

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.platform.api.dependencies.container import AppSettingsDep
from src.platform.api.request_state import set_actor_id
from src.platform.shared.authorization import ResolvePrincipalCallable
from src.platform.shared.principal import Principal
from src.platform.shared.result import Ok

_http_bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description=(
        "Paste the access_token from POST /auth/login "
        "(request body: JSON email + password)."
    ),
)


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "Not enough permissions") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _get_resolver(request: Request) -> ResolvePrincipalCallable:
    resolver = getattr(request.app.state, "principal_resolver", None)
    if resolver is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Principal resolver not configured",
        )
    return resolver  # type: ignore[return-value]


def get_current_principal(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)] = None,
) -> Principal:
    """Resolve the authenticated principal via ``app.state.principal_resolver``.

    Raises:
        HTTPException 401: Token missing, invalid, or resolver returns Err.
    """
    if creds is None:
        raise _credentials_exception()
    resolver = _get_resolver(request)
    result = resolver(creds.credentials)
    match result:
        case Ok(value=principal):
            set_actor_id(request, principal.user_id)
            return principal
        case _:
            raise _credentials_exception()


CurrentPrincipalDep: TypeAlias = Annotated[Principal, Depends(get_current_principal)]


def build_principal_dependency(
    resolver: ResolvePrincipalCallable,
) -> Callable[..., Principal]:
    """Build a FastAPI dependency function bound to a concrete resolver.

    Use this when the resolver is known at composition time (e.g., a specific
    use-case instance).  The returned callable accepts ``(request, creds)``
    and raises 401 on failure.
    """

    def _dep(
        request: Request,
        creds: Annotated[
            HTTPAuthorizationCredentials | None, Depends(_http_bearer)
        ] = None,
    ) -> Principal:
        if creds is None:
            raise _credentials_exception()
        result = resolver(creds.credentials)
        match result:
            case Ok(value=principal):
                set_actor_id(request, principal.user_id)
                return principal
            case _:
                raise _credentials_exception()

    return _dep


def require_permissions(*permissions: str) -> Any:
    """Return a Depends that requires the principal to hold **all** permissions."""
    required = set(permissions)

    def dependency(
        principal: CurrentPrincipalDep, settings: AppSettingsDep
    ) -> Principal:
        if not settings.auth_rbac_enabled:
            return principal
        if not required.issubset(principal.permissions):
            raise _forbidden()
        return principal

    return Depends(dependency)


def require_any_permission(*permissions: str) -> Any:
    """Return a Depends that requires at least **one** of the given permissions."""
    required = set(permissions)

    def dependency(
        principal: CurrentPrincipalDep, settings: AppSettingsDep
    ) -> Principal:
        if not settings.auth_rbac_enabled:
            return principal
        if not required.intersection(principal.permissions):
            raise _forbidden()
        return principal

    return Depends(dependency)


def require_roles(*roles: str) -> Any:
    """Return a Depends that requires the principal to hold at least one role."""
    required = set(roles)

    def dependency(
        principal: CurrentPrincipalDep, settings: AppSettingsDep
    ) -> Principal:
        if not settings.auth_rbac_enabled:
            return principal
        if not required.intersection(principal.roles):
            raise _forbidden("Not enough roles")
        return principal

    return Depends(dependency)


__all__ = [
    "CurrentPrincipalDep",
    "build_principal_dependency",
    "get_current_principal",
    "require_any_permission",
    "require_permissions",
    "require_roles",
]
