"""Base64 keyset cursor codec for the admin audit-log endpoint.

The audit-event ``id`` is a UUID rather than a monotonic bigserial, so
the cursor carries ``(created_at, id)`` rather than just an integer id.
That mirrors the users-feature cursor scheme.

The cursor is an opaque base64-encoded JSON payload of
``{"created_at": <iso8601>, "id": <uuid>}``. Keeping the on-the-wire
form opaque lets the cursor shape evolve without forcing client-side
changes.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from uuid import UUID


class InvalidCursorError(ValueError):
    """Raised when a cursor cannot be decoded.

    The HTTP layer maps this to ``400 Bad Request`` (Problem Details);
    no SQL is executed for malformed input.
    """


def encode_cursor(created_at: datetime, event_id: UUID) -> str:
    """Encode ``(created_at, event_id)`` as a URL-safe base64 string."""
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(event_id)},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(token: str) -> tuple[datetime, UUID]:
    """Decode a cursor token. Raises :class:`InvalidCursorError` on any error."""
    if not token:
        raise InvalidCursorError("cursor must not be empty")
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
        raise InvalidCursorError("cursor is not valid base64") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidCursorError("cursor payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidCursorError("cursor payload must be a JSON object")
    created_raw = payload.get("created_at")
    id_raw = payload.get("id")
    if not isinstance(created_raw, str) or not isinstance(id_raw, str):
        raise InvalidCursorError("cursor missing required fields")
    try:
        created_at = datetime.fromisoformat(created_raw)
    except ValueError as exc:
        raise InvalidCursorError("cursor created_at is not a valid datetime") from exc
    try:
        event_id = UUID(id_raw)
    except ValueError as exc:
        raise InvalidCursorError("cursor id is not a valid UUID") from exc
    return created_at, event_id


__all__ = ["InvalidCursorError", "decode_cursor", "encode_cursor"]
