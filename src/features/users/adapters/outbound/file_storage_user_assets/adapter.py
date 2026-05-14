"""Default :class:`UserAssetsCleanupPort` implementation.

Walks the ``users/{user_id}/`` prefix on a :class:`FileStoragePort`
and deletes every blob it finds. Used by the
``delete_user_assets`` outbox job handler.

The per-user prefix is a convention every feature that uploads
user-owned blobs MUST follow if they want their blobs reclaimed at
account deactivation/erasure time. Features that diverge ship their
own cleanup adapter and register it instead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.file_storage.application.ports.file_storage_port import FileStoragePort
from features.users.application.ports.user_assets_cleanup_port import (
    AssetsCleanupBackendError,
    AssetsCleanupError,
)

_logger = logging.getLogger("features.users.file_storage_user_assets")


def user_prefix(user_id: UUID) -> str:
    """Return the canonical per-user blob prefix.

    Used by both writers (so uploads land under the right prefix) and
    by :class:`FileStorageUserAssetsAdapter` (so cleanup discovers
    them). Lives next to the adapter so the convention has exactly
    one source of truth.
    """
    return f"users/{user_id}/"


@dataclass(slots=True)
class FileStorageUserAssetsAdapter:
    """Delete every blob under ``users/{user_id}/`` on the wired port."""

    _storage: FileStoragePort

    def delete_user_assets(self, user_id: UUID) -> Result[None, AssetsCleanupError]:
        prefix = user_prefix(user_id)
        list_result = self._storage.list(prefix)
        if isinstance(list_result, Err):
            return Err(AssetsCleanupBackendError(reason=str(list_result.error)))
        keys = list(list_result.value)
        if not keys:
            # Empty-prefix path: idempotent no-op. Returning Ok here
            # is what lets the outbox row reach ``delivered`` on the
            # first tick for users who never uploaded anything.
            return Ok(None)
        for key in keys:
            delete_result = self._storage.delete(key)
            if isinstance(delete_result, Err):
                # Surface the first failure so the relay can retry the
                # whole row under its exponential backoff. Repeated
                # deliveries are safe — delete is idempotent on the
                # port and the still-present keys are re-discovered on
                # the next attempt.
                _logger.warning(
                    "event=users.assets.delete_failed user_id=%s key=%s reason=%s",
                    user_id,
                    key,
                    delete_result.error,
                )
                return Err(AssetsCleanupBackendError(reason=str(delete_result.error)))
        _logger.info(
            "event=users.assets.deleted user_id=%s count=%d",
            user_id,
            len(keys),
        )
        return Ok(None)
