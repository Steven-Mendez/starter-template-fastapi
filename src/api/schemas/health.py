from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthPersistence(BaseModel):
    backend: Literal["inmemory", "sqlite", "postgresql"]
    ready: bool


class HealthRead(BaseModel):
    status: Literal["ok", "degraded"]
    persistence: HealthPersistence
