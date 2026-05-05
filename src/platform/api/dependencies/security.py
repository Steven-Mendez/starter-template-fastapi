from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import Depends, Header, HTTPException, Request, status

from src.platform.api.dependencies.container import get_app_settings


def require_write_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
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
