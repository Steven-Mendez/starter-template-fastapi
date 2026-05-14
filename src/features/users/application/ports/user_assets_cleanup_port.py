"""Inbound port for deleting every blob owned by a user.

Account lifecycle (deactivate, erase) needs to release storage held by
the user. The use case does not own that work directly; it enqueues a
``delete_user_assets`` job through the outbox, and the worker handler
resolves an implementation of this port and invokes
:meth:`delete_user_assets`.

The default adapter (:class:`FileStorageUserAssetsAdapter`) walks the
per-user prefix ``users/{user_id}/`` on the wired
:class:`FileStoragePort`. Features that store user-owned blobs elsewhere
ship their own implementation and register it in their composition root.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app_platform.shared.errors import ApplicationError
from app_platform.shared.result import Result


class AssetsCleanupError(ApplicationError):
    """Base class for asset-cleanup errors returned as ``Err`` values."""


@dataclass(frozen=True, slots=True)
class AssetsCleanupBackendError(AssetsCleanupError):
    """Raised when the underlying storage backend failed during cleanup."""

    reason: str

    def __str__(self) -> str:
        return f"User-asset cleanup backend failure: {self.reason}"


class UserAssetsCleanupPort(Protocol):
    """Delete every blob owned by a user.

    Implementations MUST be idempotent on the user id: when the user
    has no blobs (already cleaned, or never had any), the call MUST
    return ``Ok(None)`` rather than raising. That makes the outbox
    relay's at-least-once redelivery safe — a second invocation for
    the same id is always a no-op.
    """

    def delete_user_assets(self, user_id: UUID) -> Result[None, AssetsCleanupError]:
        """Delete every blob owned by ``user_id``.

        Returns ``Ok(None)`` on success (including the no-blobs case).
        Returns ``Err(AssetsCleanupError)`` when a transient backend
        failure prevents cleanup; the relay will retry under its
        configured backoff.
        """
        ...
