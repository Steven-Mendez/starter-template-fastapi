"""Domain representation of a row in ``outbox_messages``.

The domain object is intentionally framework-free: it is a plain
dataclass that adapters convert to and from their persistence model.
The dispatch use case operates on these objects and never sees the
SQLModel table directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from features.outbox.domain.status import OutboxStatus


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    """A single side-effect intent recorded by a producer transaction."""

    id: UUID
    job_name: str
    payload: dict[str, Any]
    available_at: datetime
    status: OutboxStatus
    attempts: int
    last_error: str | None
    locked_at: datetime | None
    locked_by: str | None
    created_at: datetime
    dispatched_at: datetime | None
