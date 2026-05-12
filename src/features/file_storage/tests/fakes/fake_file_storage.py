"""In-memory :class:`FileStoragePort` for unit and e2e tests.

Keeps every stored blob in a dict keyed by string. Returns the same
shape of :class:`Result` the real adapters do, so use cases can be
exercised against the fake without behavioural drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.features.file_storage.application.errors import (
    FileStorageError,
    ObjectNotFoundError,
    StorageBackendError,
)
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class _StoredObject:
    content: bytes
    content_type: str


@dataclass(slots=True)
class FakeFileStorage:
    """Dict-backed fake of :class:`FileStoragePort`."""

    objects: dict[str, _StoredObject] = field(default_factory=dict)

    def put(
        self,
        key: str,
        content: bytes,
        content_type: str,
    ) -> Result[None, FileStorageError]:
        self.objects[key] = _StoredObject(content=content, content_type=content_type)
        return Ok(None)

    def get(self, key: str) -> Result[bytes, FileStorageError]:
        obj = self.objects.get(key)
        if obj is None:
            return Err(ObjectNotFoundError(key=key))
        return Ok(obj.content)

    def delete(self, key: str) -> Result[None, FileStorageError]:
        self.objects.pop(key, None)
        return Ok(None)

    def signed_url(
        self,
        key: str,
        expires_in: int,
    ) -> Result[str, FileStorageError]:
        if expires_in <= 0:
            return Err(StorageBackendError(reason="expires_in must be positive"))
        if key not in self.objects:
            return Err(ObjectNotFoundError(key=key))
        return Ok(f"memory://{key}")

    def reset(self) -> None:
        self.objects.clear()
