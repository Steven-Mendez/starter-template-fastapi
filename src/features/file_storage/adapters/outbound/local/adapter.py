"""Filesystem-backed :class:`FileStoragePort` for development and tests.

Object keys are hashed with sha256 to derive a two-level prefix
(``ab/cd/<hash>``) before writing under ``APP_STORAGE_LOCAL_PATH``.
The prefix layout avoids pathological directory sizes when consumers
generate many keys with a shared root (e.g. ``user/<id>/avatar``),
since filesystems degrade once a single directory holds millions of
entries. The original key is preserved in a sidecar file so
:meth:`get`/:meth:`delete` can resolve it deterministically.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.features.file_storage.application.errors import (
    FileStorageError,
    ObjectNotFoundError,
    StorageBackendError,
)
from src.platform.shared.result import Err, Ok, Result

_logger = logging.getLogger("src.features.file_storage.local")

_METADATA_SUFFIX = ".meta.json"


@dataclass(slots=True)
class LocalFileStorageAdapter:
    """Write objects to ``root`` on the local filesystem."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"APP_STORAGE_LOCAL_PATH {self.root!s} is not writable: {exc}"
            ) from exc

    def put(
        self,
        key: str,
        content: bytes,
        content_type: str,
    ) -> Result[None, FileStorageError]:
        path = self._object_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            self._metadata_path(key).write_text(
                json.dumps({"key": key, "content_type": content_type}),
                encoding="utf-8",
            )
        except OSError as exc:
            _logger.warning(
                "event=file_storage.local.put_failed key=%s reason=%s", key, exc
            )
            return Err(StorageBackendError(reason=str(exc)))
        return Ok(None)

    def get(self, key: str) -> Result[bytes, FileStorageError]:
        path = self._object_path(key)
        if not path.exists():
            return Err(ObjectNotFoundError(key=key))
        try:
            return Ok(path.read_bytes())
        except OSError as exc:
            return Err(StorageBackendError(reason=str(exc)))

    def delete(self, key: str) -> Result[None, FileStorageError]:
        path = self._object_path(key)
        meta = self._metadata_path(key)
        try:
            path.unlink(missing_ok=True)
            meta.unlink(missing_ok=True)
        except OSError as exc:
            return Err(StorageBackendError(reason=str(exc)))
        return Ok(None)

    def signed_url(
        self,
        key: str,
        expires_in: int,
    ) -> Result[str, FileStorageError]:
        # ``expires_in`` has no meaning on the local backend (there is
        # no signer), but the port accepts it so the call site stays
        # uniform with the s3 implementation. The value is intentionally
        # ignored after a minimal range check.
        if expires_in <= 0:
            return Err(StorageBackendError(reason="expires_in must be positive"))
        path = self._object_path(key)
        if not path.exists():
            return Err(ObjectNotFoundError(key=key))
        return Ok(path.resolve().as_uri())

    def reset(self) -> None:
        """Wipe the storage root. Test-only convenience."""
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _object_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / digest[:2] / digest[2:4] / digest

    def _metadata_path(self, key: str) -> Path:
        return self._object_path(key).with_suffix(_METADATA_SUFFIX)
