"""Pydantic HTTP schema for Kanban health payloads."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthPersistence(BaseModel):
    """Per-backend readiness payload included inside :class:`HealthRead`."""

    backend: str
    ready: bool


class HealthRedis(BaseModel):
    """Redis liveness payload included inside :class:`HealthRead` when configured."""

    configured: bool
    ready: bool


class HealthAuth(BaseModel):
    """Auth-specific readiness signals surfaced by the health endpoint."""

    jwt_secret_configured: bool
    principal_cache_ready: bool
    rate_limiter_backend: Literal["in_memory", "redis"]
    rate_limiter_ready: bool


class HealthRead(BaseModel):
    """Top-level response shape for the readiness endpoint."""

    status: Literal["ok", "degraded"]
    persistence: HealthPersistence
    auth: HealthAuth
    redis: HealthRedis | None = None


class HealthLive(BaseModel):
    """Minimal response shape for the liveness probe.

    Only confirms the process is accepting requests — no external deps
    are checked so orchestrators can distinguish process crashes from
    dependency failures and avoid unnecessary restarts.
    """

    status: Literal["ok"] = "ok"
