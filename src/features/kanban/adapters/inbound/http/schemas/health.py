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


class HealthRead(BaseModel):
    """Top-level response shape for the readiness endpoint."""

    status: Literal["ok", "degraded"]
    persistence: HealthPersistence
    redis: HealthRedis | None = None
