"""Dependency for the optional long-lived Redis client stored on app state."""

from __future__ import annotations

from typing import Annotated, TypeAlias

import redis as redis_lib
from fastapi import Depends, Request


def get_app_redis_client(request: Request) -> redis_lib.Redis | None:  # type: ignore[type-arg]
    """Return the long-lived Redis client from ``app.state``, or ``None``.

    The client is created during lifespan startup when ``APP_AUTH_REDIS_URL``
    is configured and stored on ``app.state.redis_client``. Returns ``None``
    when Redis is not configured.
    """
    return getattr(request.app.state, "redis_client", None)


AppRedisClientDep: TypeAlias = Annotated[
    redis_lib.Redis | None, Depends(get_app_redis_client)  # type: ignore[type-arg]
]
