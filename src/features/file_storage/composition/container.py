"""Composition root for the file-storage feature.

Selects the active adapter based on :class:`StorageSettings.backend`
and returns a :class:`FileStorageContainer` exposing the port. The
container is built unconditionally so consumer features can take the
port as a dependency without knowing which backend is wired.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.features.file_storage.adapters.outbound.local import LocalFileStorageAdapter
from src.features.file_storage.adapters.outbound.s3 import S3FileStorageAdapter
from src.features.file_storage.application.ports.file_storage_port import (
    FileStoragePort,
)
from src.features.file_storage.composition.settings import StorageSettings


@dataclass(slots=True)
class FileStorageContainer:
    """Wired :class:`FileStoragePort` plus the settings used to build it."""

    settings: StorageSettings
    port: FileStoragePort


def build_file_storage_container(settings: StorageSettings) -> FileStorageContainer:
    """Build the file-storage feature's container."""
    port: FileStoragePort
    if settings.backend == "local":
        if not settings.local_path:
            raise RuntimeError(
                "APP_STORAGE_LOCAL_PATH is required when APP_STORAGE_BACKEND=local"
            )
        port = LocalFileStorageAdapter(root=Path(settings.local_path))
    elif settings.backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError(
                "APP_STORAGE_S3_BUCKET is required when APP_STORAGE_BACKEND=s3"
            )
        port = S3FileStorageAdapter(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
        )
    else:  # pragma: no cover - guarded by StorageSettings construction
        raise RuntimeError(f"Unknown storage backend: {settings.backend!r}")

    return FileStorageContainer(settings=settings, port=port)
