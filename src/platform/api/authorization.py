"""FastAPI-bound authorization dependencies for the platform layer.

The platform exposes two building blocks:

* ``get_current_principal`` resolves the JWT bearer token via the
  resolver registered on ``request.app.state.principal_resolver``.
  No feature import is needed — the resolver is wired by the auth
  feature inside the lifespan, and tests can register a fake.
* ``require_authorization`` builds a FastAPI dependency that calls
  ``AuthorizationPort.check`` for the (action, resource_type, resource_id)
  triple identified at request time. Resource ids are extracted by a
  caller-supplied ``id_loader``; system-level routes use the sentinel
  ``"main"`` and pass ``id_loader=None``.

ReBAC checks are resource-scoped: the deny path returns 403; missing
credentials return 401.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, TypeAlias

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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


def _forbidden(detail: str = "Permission denied") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _get_resolver(request: Request) -> ResolvePrincipalCallable:
    resolver = getattr(request.app.state, "principal_resolver", None)
    if resolver is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Principal resolver not configured",
        )
    return resolver  # type: ignore[return-value]


def _get_authorization(request: Request) -> Any:
    """Return the AuthorizationPort registered on app.state, or raise 503.

    Typed as ``Any`` so the platform avoids importing from a feature.
    The auth feature attaches its concrete adapter during lifespan.
    """
    authz = getattr(request.app.state, "authorization", None)
    if authz is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization port not configured",
        )
    return authz


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


def require_authorization(
    action: str,
    resource_type: str,
    id_loader: Callable[[Request], str] | None = None,
) -> Any:
    """Return a FastAPI dependency that gates a route on a ReBAC check.

    Behaviour:

    * Resolves the current principal (raising 401 if missing/invalid).
    * Computes the resource id via ``id_loader(request)`` or uses the
      sentinel ``"main"`` when ``id_loader`` is ``None`` (system-level routes).
    * Calls ``AuthorizationPort.check(user_id, action, resource_type, resource_id)``.
    * Raises 403 on deny.

    Args:
        action: The action name as declared in
            ``src/features/auth/application/authorization/actions.py``.
        resource_type: The resource type the action targets
            (e.g. ``"kanban"``, ``"system"``, ``"column"``, ``"card"``).
        id_loader: Callable that extracts the resource id from the request
            (typically a one-line lambda reading ``request.path_params``).
            Pass ``None`` for system-level routes; the sentinel ``"main"``
            is used.

    Returns:
        A FastAPI ``Depends`` object suitable for the ``dependencies=[...]``
        argument of a route decorator.
    """

    def dependency(
        request: Request,
        principal: CurrentPrincipalDep,
    ) -> Principal:
        authz = _get_authorization(request)
        resource_id = id_loader(request) if id_loader is not None else "main"
        allowed = authz.check(
            user_id=principal.user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if not allowed:
            raise _forbidden()
        return principal

    return Depends(dependency)


__all__ = [
    "CurrentPrincipalDep",
    "build_principal_dependency",
    "get_current_principal",
    "require_authorization",
]
