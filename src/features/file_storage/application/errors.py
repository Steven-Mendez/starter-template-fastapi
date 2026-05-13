"""Application-layer errors for the file-storage feature."""

from __future__ import annotations

from dataclasses import dataclass

from app_platform.shared.errors import ApplicationError


class FileStorageError(ApplicationError):
    """Base class for file-storage errors returned as ``Err`` values."""


@dataclass(frozen=True, slots=True)
class ObjectNotFoundError(FileStorageError):
    """Raised when a requested key has no stored object."""

    key: str

    def __str__(self) -> str:
        return f"No stored object for key: {self.key!r}"


@dataclass(frozen=True, slots=True)
class StorageBackendError(FileStorageError):
    """Raised when the underlying backend fails (IO error, S3 5xx, etc.)."""

    reason: str

    def __str__(self) -> str:
        return f"Storage backend failure: {self.reason}"
