"""Inbound port producer use cases call to record a side-effect intent.

The contract is "write a row that becomes visible to the relay iff the
caller's transaction commits". The adapter implementing this Protocol
MUST stage the write on a session passed in by the caller; it MUST
NOT commit or open its own transaction. That session-scoping is what
gives the outbox its atomic guarantee — the side-effect row goes in
the same ``INSERT`` batch as the business state and rolls back with
it on failure.

The ``available_at`` parameter lets a producer schedule a side effect
for the future. ``None`` means "as soon as the relay can claim it".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class OutboxPort(Protocol):
    """Stage a pending outbox row on the caller's transaction."""

    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None:
        """Record a pending side effect.

        The implementation MUST attach the new row to the session
        passed in at adapter construction time and MUST NOT commit or
        flush on its own. ``available_at`` defaults to "now" at the
        database (whenever the relay next runs the claim query). When
        non-``None``, the value MUST be timezone-aware; the SQLModel
        adapter rejects naive datetimes.
        """
        ...
