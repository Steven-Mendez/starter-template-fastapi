"""Targeted unit tests for :class:`S3FileStorageAdapter` error mapping.

The shared contract suite covers the happy paths against a ``moto``
mock. These tests focus on the edges that are too narrow or too
backend-specific for the contract: arbitrary ``ClientError`` codes,
transport failures, and the ``expires_in`` guard.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from moto import mock_aws

from app_platform.shared.result import Err, Ok
from features.file_storage.adapters.outbound.s3 import S3FileStorageAdapter
from features.file_storage.application.errors import (
    ObjectNotFoundError,
    StorageBackendError,
)

pytestmark = pytest.mark.unit


_BUCKET = "unit-test"
_REGION = "us-east-1"


def _client_error(code: str, message: str = "boom", status: int = 400) -> ClientError:
    response: Any = {
        "Error": {"Code": code, "Message": message},
        "ResponseMetadata": {"HTTPStatusCode": status},
    }
    return ClientError(error_response=response, operation_name="GetObject")


def test_get_no_such_key_maps_to_object_not_found_error() -> None:
    with mock_aws():
        client = boto3.client("s3", region_name=_REGION)
        client.create_bucket(Bucket=_BUCKET)
        adapter = S3FileStorageAdapter(bucket=_BUCKET, region=_REGION, client=client)

        result = adapter.get("never-stored")

    assert isinstance(result, Err)
    assert isinstance(result.error, ObjectNotFoundError)
    assert result.error.key == "never-stored"


def test_get_arbitrary_client_error_maps_to_storage_backend_error() -> None:
    client = MagicMock()
    client.get_object.side_effect = _client_error("AccessDenied", "nope", status=403)
    adapter = S3FileStorageAdapter(bucket=_BUCKET, region=_REGION, client=client)

    result = adapter.get("k")

    assert isinstance(result, Err)
    assert isinstance(result.error, StorageBackendError)
    assert "AccessDenied" in result.error.reason
    assert "nope" in result.error.reason


def test_put_botocore_error_maps_to_storage_backend_error() -> None:
    client = MagicMock()
    client.put_object.side_effect = EndpointConnectionError(
        endpoint_url="https://s3.amazonaws.com"
    )
    adapter = S3FileStorageAdapter(bucket=_BUCKET, region=_REGION, client=client)

    result = adapter.put("k", b"x", "text/plain")

    assert isinstance(result, Err)
    assert isinstance(result.error, StorageBackendError)


def test_signed_url_rejects_expires_in_above_seven_days() -> None:
    client = MagicMock()
    adapter = S3FileStorageAdapter(bucket=_BUCKET, region=_REGION, client=client)

    result = adapter.signed_url("k", expires_in=604801)

    assert isinstance(result, Err)
    assert isinstance(result.error, StorageBackendError)
    assert "604800" in result.error.reason
    # The guard must short-circuit before either S3 round-trip.
    client.head_object.assert_not_called()
    client.generate_presigned_url.assert_not_called()


def test_signed_url_missing_key_maps_to_object_not_found_error() -> None:
    with mock_aws():
        client = boto3.client("s3", region_name=_REGION)
        client.create_bucket(Bucket=_BUCKET)
        adapter = S3FileStorageAdapter(bucket=_BUCKET, region=_REGION, client=client)

        result = adapter.signed_url("missing", expires_in=60)

    assert isinstance(result, Err)
    assert isinstance(result.error, ObjectNotFoundError)


def test_signed_url_happy_path_returns_string() -> None:
    with mock_aws():
        client = boto3.client("s3", region_name=_REGION)
        client.create_bucket(Bucket=_BUCKET)
        client.put_object(Bucket=_BUCKET, Key="k", Body=b"x")
        adapter = S3FileStorageAdapter(bucket=_BUCKET, region=_REGION, client=client)

        result = adapter.signed_url("k", expires_in=60)

    assert isinstance(result, Ok)
    assert result.value.startswith("https://")
