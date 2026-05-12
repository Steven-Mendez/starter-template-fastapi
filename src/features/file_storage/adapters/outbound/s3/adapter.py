"""Stub :class:`FileStoragePort` for Amazon S3.

This adapter exists so the port has a registered production-shaped
implementation while a consumer project decides which object store
they want. Every method raises :class:`NotImplementedError` with a
pointer at ``README.md`` in this directory, which spells out the
boto3 mapping and the IAM policy a real implementation needs.

Mirrors the SpiceDB authorization adapter stub: the type-checker keeps
the signature honest, contract tests confirm the methods exist, and
production startup refuses ``APP_STORAGE_BACKEND=s3`` until the methods
are filled in.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.features.file_storage.application.errors import FileStorageError
from src.platform.shared.result import Result

_README_HINT = (
    "See src/features/file_storage/adapters/outbound/s3/README.md "
    "for the boto3 mapping and IAM requirements."
)


@dataclass(slots=True)
class S3FileStorageAdapter:
    """Stub S3-backed :class:`FileStoragePort` — every method raises."""

    bucket: str
    region: str

    def put(
        self,
        key: str,
        content: bytes,
        content_type: str,
    ) -> Result[None, FileStorageError]:
        raise NotImplementedError(
            f"S3FileStorageAdapter.put is not implemented. {_README_HINT}"
        )

    def get(self, key: str) -> Result[bytes, FileStorageError]:
        raise NotImplementedError(
            f"S3FileStorageAdapter.get is not implemented. {_README_HINT}"
        )

    def delete(self, key: str) -> Result[None, FileStorageError]:
        raise NotImplementedError(
            f"S3FileStorageAdapter.delete is not implemented. {_README_HINT}"
        )

    def signed_url(
        self,
        key: str,
        expires_in: int,
    ) -> Result[str, FileStorageError]:
        raise NotImplementedError(
            f"S3FileStorageAdapter.signed_url is not implemented. {_README_HINT}"
        )
