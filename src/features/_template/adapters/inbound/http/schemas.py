"""Pydantic schemas for the ``/things`` API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateThingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class UpdateThingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ThingResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


class ListThingsResponse(BaseModel):
    items: list[ThingResponse]


class AttachmentResponse(BaseModel):
    thing_id: UUID
    key: str
    content_type: str
    size_bytes: int
