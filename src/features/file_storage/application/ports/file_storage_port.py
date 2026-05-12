"""Inbound port the rest of the application calls to store and retrieve blobs.

The port is intentionally narrow — four methods covering the upload,
download, delete, and link-out flows that every consumer needs.
Adapters translate between the port and a concrete storage transport
(local filesystem, S3, GCS, …).
"""

from __future__ import annotations

from typing import Protocol

from src.features.file_storage.application.errors import FileStorageError
from src.platform.shared.result import Result


class FileStoragePort(Protocol):
    """Store, fetch, and delete opaque byte blobs keyed by string."""

    def put(
        self,
        key: str,
        content: bytes,
        content_type: str,
    ) -> Result[None, FileStorageError]:
        """Store ``content`` under ``key``.

        Overwrites any existing object at the same key. ``content_type``
        is retained alongside the blob where the backend supports it
        (S3 ``Content-Type``); the local adapter stores it in a sidecar
        for the future ``signed_url`` consumer to read.
        """
        ...

    def get(self, key: str) -> Result[bytes, FileStorageError]:
        """Return the bytes stored under ``key``.

        Returns an :class:`Err` wrapping :class:`ObjectNotFoundError`
        when no object exists at that key.
        """
        ...

    def delete(self, key: str) -> Result[None, FileStorageError]:
        """Remove the object stored under ``key``.

        Deleting a missing key is a no-op (returns :class:`Ok`); this
        keeps idempotent cleanup workflows simple.
        """
        ...

    def signed_url(
        self,
        key: str,
        expires_in: int,
    ) -> Result[str, FileStorageError]:
        """Return a URL the consumer can serve to clients for ``expires_in`` seconds.

        For the S3 adapter this is a presigned GET URL. For the local
        adapter it is a ``file://`` URL pointing at the on-disk path —
        consumers that want to expose downloads over HTTP wrap this in
        their own route (the local backend is dev-only).
        """
        ...
