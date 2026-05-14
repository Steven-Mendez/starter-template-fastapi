"""GDPR Art. 15 export: serialize a user's data and return a signed URL.

The export is intentionally a single JSON blob written to the wired
:class:`FileStoragePort`. The HTTP response carries only a signed URL
+ expiry; large fields (profile data, audit history, file metadata)
travel through storage, not the API edge.

Synchronous by default — the blob is typically small (<1 MB) and the
``signed_url`` pattern decouples the response from the blob size. If
profiling later shows the synchronous path is too slow, the use case
can be moved behind a job + status endpoint without changing the
response shape (clients only see ``download_url`` / ``expires_at``).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app_platform.shared.result import Err, Ok, Result
from features.file_storage.application.ports.file_storage_port import FileStoragePort
from features.users.application.errors import UserError, UserNotFoundError
from features.users.application.ports.user_audit_reader_port import (
    UserAuditReaderPort,
)
from features.users.application.ports.user_port import UserPort

_logger = logging.getLogger("features.users.export_user_data")

# Signed-URL TTL is fixed at 15 minutes — long enough for a UI to fetch
# and stream the blob, short enough that an intercepted URL stops
# working before the user notices. Mirrored in the spec scenario.
_EXPORT_URL_TTL_SECONDS = 900


class ExportUserDataError(UserError):
    """Base class for export-pipeline errors."""


@dataclass(frozen=True, slots=True)
class StorageWriteFailed(ExportUserDataError):
    """The export blob could not be written to file storage."""

    reason: str

    def __str__(self) -> str:
        return f"Export storage write failed: {self.reason}"

    def __reduce__(self) -> tuple[type, tuple[str]]:
        # See ``ApplicationError`` docstring: must be picklable for arq.
        return (type(self), (self.reason,))


@dataclass(frozen=True, slots=True)
class SignedUrlFailed(ExportUserDataError):
    """The export blob was written but the signed URL could not be issued."""

    reason: str

    def __str__(self) -> str:
        return f"Export signed-url issuance failed: {self.reason}"

    def __reduce__(self) -> tuple[type, tuple[str]]:
        return (type(self), (self.reason,))


@dataclass(frozen=True, slots=True)
class ExportContract:
    """Use-case return shape mapped 1:1 to the HTTP response body."""

    download_url: str
    expires_at: datetime


@dataclass(slots=True)
class ExportUserData:
    """Assemble the export JSON and hand back a signed URL.

    The use case is read-only with respect to user state. Anything the
    user produced that this service still holds is gathered through
    narrow ports — the file-listing port discovers blob keys under
    ``users/{user_id}/``; the audit-reader port returns JSON-safe
    audit events.
    """

    _users: UserPort
    _file_storage: FileStoragePort
    _audit_reader: UserAuditReaderPort

    def execute(self, user_id: UUID) -> Result[ExportContract, UserError]:
        # ``get_raw_by_id`` so an erased user does not silently look
        # like "no such user" — but in practice an erased user's
        # authenticated session is already dead, so this branch is
        # mostly defensive.
        existing = self._users.get_raw_by_id(user_id)
        if existing is None:
            return Err(UserNotFoundError())

        blob = _build_export_payload(
            user=existing,
            audit_events=self._audit_reader.list_for_user(user_id),
            file_keys=_list_user_files(self._file_storage, user_id),
        )
        content = json.dumps(blob, sort_keys=True, default=str).encode("utf-8")
        key = f"exports/{user_id}/{uuid4()}.json"
        put_result = self._file_storage.put(key, content, "application/json")
        if isinstance(put_result, Err):
            _logger.error(
                "event=users.export.put_failed user_id=%s reason=%s",
                user_id,
                put_result.error,
            )
            return Err(StorageWriteFailed(reason=str(put_result.error)))
        url_result = self._file_storage.signed_url(
            key, expires_in=_EXPORT_URL_TTL_SECONDS
        )
        if isinstance(url_result, Err):
            _logger.error(
                "event=users.export.signed_url_failed user_id=%s reason=%s",
                user_id,
                url_result.error,
            )
            return Err(SignedUrlFailed(reason=str(url_result.error)))
        expires_at = datetime.now(UTC) + timedelta(seconds=_EXPORT_URL_TTL_SECONDS)
        return Ok(
            ExportContract(
                download_url=url_result.value,
                expires_at=expires_at,
            )
        )


def _list_user_files(
    file_storage: FileStoragePort, user_id: UUID
) -> list[dict[str, Any]]:
    """Return JSON-safe metadata for every blob owned by ``user_id``.

    Mirrors the prefix layout used by :class:`FileStorageUserAssetsAdapter`
    so the export sees the same set of blobs the cleanup pipeline does.
    A best-effort empty list is returned when the backend fails so the
    export still produces a JSON document (and the user can re-export
    after the operator fixes the backend).
    """
    prefix = f"users/{user_id}/"
    result = file_storage.list(prefix)
    if isinstance(result, Err):
        _logger.warning(
            "event=users.export.list_failed user_id=%s reason=%s",
            user_id,
            result.error,
        )
        return []
    return [{"key": k} for k in result.value]


def _build_export_payload(
    *,
    user: Any,
    audit_events: list[dict[str, Any]],
    file_keys: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compose the JSON blob clients download from the signed URL.

    Keys are stable across exports so downstream tooling (CLI parsers,
    user-side scripts) can rely on the shape. The ``profile`` block is
    intentionally a flat projection of the user row; as new profile
    columns land, this list grows alongside the PII inventory.
    """
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
            "last_login_at": (
                user.last_login_at.isoformat() if user.last_login_at else None
            ),
        },
        "profile": {
            # Mirror of the user row's mutable profile fields. Today the
            # users feature stores only the email; future profile
            # columns (display name, locale, etc.) extend this block.
            "email": user.email,
        },
        "audit_events": audit_events,
        "files": file_keys,
        "exported_at": datetime.now(UTC).isoformat(),
    }
