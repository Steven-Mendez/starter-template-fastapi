"""Optional API-key gate for write endpoints in shared deployments."""

from __future__ import annotations

import secrets
from typing import Annotated, TypeAlias

from fastapi import Depends, Header, HTTPException, Request, status

from src.platform.api.dependencies.container import get_app_settings


def require_write_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Reject the request unless ``X-API-Key`` matches a configured key.

    Both ``APP_WRITE_API_KEY`` (single) and ``APP_WRITE_API_KEYS`` (list)
    contribute accepted values. Supplying multiple values lets operators
    rotate keys without downtime: deploy the new key in
    ``APP_WRITE_API_KEYS``, switch clients over, then remove the old
    ``APP_WRITE_API_KEY``.

    Acts as a no-op when no key is configured so local and template
    deployments stay open by default.

    Raises:
        HTTPException 401: If at least one key is configured but the
            header is missing or matches none of them.
    """
    settings = get_app_settings(request)
    configured: tuple[str, ...] = tuple(
        key for key in (settings.write_api_key, *settings.write_api_keys) if key
    )
    if not configured:
        return
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    # Constant-time comparison resists timing attacks that could otherwise
    # distinguish "wrong length" from "wrong content" by measuring response
    # latency. Iterating over all configured keys is acceptable because the
    # set is small (typically 1–2 during rotation).
    for accepted in configured:
        if secrets.compare_digest(x_api_key, accepted):
            return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


WriteApiKeyDep: TypeAlias = Annotated[None, Depends(require_write_api_key)]
RequireWriteApiKey = Depends(require_write_api_key)
