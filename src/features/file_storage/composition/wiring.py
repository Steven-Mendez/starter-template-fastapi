"""Wiring helpers for the file-storage feature."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI

from features.file_storage.composition.container import FileStorageContainer


def attach_file_storage_container(
    app: FastAPI, container: FileStorageContainer
) -> None:
    """Publish the :class:`FileStorageContainer` on ``app.state``."""
    app.state.file_storage_container = container


def get_file_storage_container(app: FastAPI) -> FileStorageContainer:
    """Return the previously-attached :class:`FileStorageContainer`."""
    container = getattr(app.state, "file_storage_container", None)
    if container is None:
        raise RuntimeError("FileStorageContainer has not been attached to app.state")
    return cast(FileStorageContainer, container)
