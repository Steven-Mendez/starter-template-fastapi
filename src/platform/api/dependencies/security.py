"""Optional API-key gate for write endpoints in shared deployments."""

from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import Depends, Header, HTTPException, Request, status

from src.platform.api.dependencies.container import get_app_settings


def require_write_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Reject the request unless ``X-API-Key`` matches ``APP_WRITE_API_KEY``.

    Acts as a no-op when no key is configured so local and template
    deployments stay open by default. Shared environments enable the
    guard by setting ``APP_WRITE_API_KEY``.

    Raises:
        HTTPException 401: If a key is configured but the header is
            missing or does not match.
    """
    configured_key = get_app_settings(request).write_api_key
    if not configured_key:
        return
    if x_api_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


WriteApiKeyDep: TypeAlias = Annotated[None, Depends(require_write_api_key)]
RequireWriteApiKey = Depends(require_write_api_key)
