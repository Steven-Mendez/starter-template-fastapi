"""S3-backed :class:`FileStoragePort` implementation.

Uses ``boto3``'s synchronous client. The adapter is constructed once at
composition time and held for the process lifetime; ``botocore`` clients
are threadsafe for the read paths FastAPI's threadpool uses to dispatch
sync route dependencies.

Credentials and (optionally) a custom endpoint URL come from the
standard AWS resolution chain — environment variables, shared config,
instance profile, etc. Operators pointing at R2 / MinIO / other
S3-compatible services set ``AWS_ENDPOINT_URL_S3`` rather than threading
a template-specific knob through ``StorageSettings``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app_platform.shared.result import Err, Ok, Result
from features.file_storage.application.errors import (
    FileStorageError,
    ObjectNotFoundError,
    StorageBackendError,
)

# S3 caps presigned URLs at 7 days for SigV4. Going past it returns a URL
# that fails on use rather than at signing time, so we reject up front.
_S3_PRESIGNED_URL_MAX_SECONDS = 604800

_NOT_FOUND_CODES = frozenset({"NoSuchKey", "404", "NotFound"})


def _is_not_found(exc: ClientError) -> bool:
    error = exc.response.get("Error", {}) if hasattr(exc, "response") else {}
    code = error.get("Code")
    status = str(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
    return code in _NOT_FOUND_CODES or status == "404"


@dataclass(slots=True)
class S3FileStorageAdapter:
    """Real :class:`FileStoragePort` backed by ``boto3``.

    The :class:`boto3` client is built in ``__post_init__`` from the
    region passed in by the composition root and stashed on the
    instance. Tests that want to inject a pre-built client (for
    ``moto``-mocked transports or otherwise) pass ``client=...``
    explicitly to bypass construction.
    """

    bucket: str
    region: str
    client: Any = field(default=None)

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = boto3.client("s3", region_name=self.region)

    def put(
        self,
        key: str,
        content: bytes,
        content_type: str,
    ) -> Result[None, FileStorageError]:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except ClientError as exc:
            return Err(StorageBackendError(reason=_format_client_error(exc)))
        except BotoCoreError as exc:
            return Err(StorageBackendError(reason=str(exc)))
        return Ok(None)

    def get(self, key: str) -> Result[bytes, FileStorageError]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"].read()
        except ClientError as exc:
            if _is_not_found(exc):
                return Err(ObjectNotFoundError(key=key))
            return Err(StorageBackendError(reason=_format_client_error(exc)))
        except BotoCoreError as exc:
            return Err(StorageBackendError(reason=str(exc)))
        return Ok(body)

    def delete(self, key: str) -> Result[None, FileStorageError]:
        # S3 returns 204 even when the key is absent, so this satisfies
        # the port's "delete of a missing key is a no-op" contract
        # without us having to inspect responses.
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            return Err(StorageBackendError(reason=_format_client_error(exc)))
        except BotoCoreError as exc:
            return Err(StorageBackendError(reason=str(exc)))
        return Ok(None)

    def list(self, prefix: str) -> Result[list[str], FileStorageError]:
        """Paginate ``list_objects_v2`` and return every key under ``prefix``.

        Uses the ``list_objects_v2`` paginator so buckets with more
        than 1000 matching keys are walked correctly. Returns a list
        so the caller can iterate freely.
        """
        keys: list[str] = []
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for entry in page.get("Contents") or ():
                    key = entry.get("Key")
                    if isinstance(key, str):
                        keys.append(key)
        except ClientError as exc:
            return Err(StorageBackendError(reason=_format_client_error(exc)))
        except BotoCoreError as exc:
            return Err(StorageBackendError(reason=str(exc)))
        return Ok(keys)

    def signed_url(
        self,
        key: str,
        expires_in: int,
    ) -> Result[str, FileStorageError]:
        if expires_in > _S3_PRESIGNED_URL_MAX_SECONDS:
            return Err(
                StorageBackendError(
                    reason=(
                        f"expires_in exceeds S3 maximum of "
                        f"{_S3_PRESIGNED_URL_MAX_SECONDS} seconds"
                    )
                )
            )
        # ``generate_presigned_url`` signs blindly — it returns a URL
        # even for a missing key. ``LocalFileStorageAdapter`` errors in
        # that case, so we ``head_object`` first to keep the contracts
        # aligned across adapters.
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if _is_not_found(exc):
                return Err(ObjectNotFoundError(key=key))
            return Err(StorageBackendError(reason=_format_client_error(exc)))
        except BotoCoreError as exc:
            return Err(StorageBackendError(reason=str(exc)))
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError as exc:
            return Err(StorageBackendError(reason=_format_client_error(exc)))
        except BotoCoreError as exc:
            return Err(StorageBackendError(reason=str(exc)))
        return Ok(url)


def _format_client_error(exc: ClientError) -> str:
    error = exc.response.get("Error", {}) if hasattr(exc, "response") else {}
    code = error.get("Code", "Unknown")
    message = error.get("Message", str(exc))
    return f"{code}: {message}"
