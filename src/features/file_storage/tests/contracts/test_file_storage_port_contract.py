"""Behavioural contract shared by every :class:`FileStoragePort` implementation.

The fake, the local on-disk adapter, and the S3 adapter (backed by
``moto``'s in-process AWS mock) are exercised against the same
scenarios. A regression on any backend surfaces here.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Callable

import boto3
import pytest
from moto import mock_aws

from app_platform.shared.result import Err, Ok
from features.file_storage.adapters.outbound.local import LocalFileStorageAdapter
from features.file_storage.adapters.outbound.s3 import S3FileStorageAdapter
from features.file_storage.application.errors import (
    ObjectNotFoundError,
)
from features.file_storage.application.ports.file_storage_port import (
    FileStoragePort,
)
from features.file_storage.tests.fakes.fake_file_storage import FakeFileStorage

pytestmark = pytest.mark.unit


AdapterFactory = Callable[[Path], FileStoragePort]

_S3_TEST_BUCKET = "contract-test"
_S3_TEST_REGION = "us-east-1"


@pytest.fixture(autouse=True)
def _aws_mock() -> Iterator[None]:
    """Wrap every contract test in moto's AWS mock.

    The fake and local adapters do not touch AWS, so an always-on mock
    costs nothing for them; the S3 factory below relies on it.
    """
    with mock_aws():
        client = boto3.client("s3", region_name=_S3_TEST_REGION)
        client.create_bucket(Bucket=_S3_TEST_BUCKET)
        yield


def _fake_factory(_: Path) -> FileStoragePort:
    return FakeFileStorage()


def _local_factory(tmp_path: Path) -> FileStoragePort:
    return LocalFileStorageAdapter(root=tmp_path / "storage")


def _s3_factory(_: Path) -> FileStoragePort:
    client = boto3.client("s3", region_name=_S3_TEST_REGION)
    return S3FileStorageAdapter(
        bucket=_S3_TEST_BUCKET,
        region=_S3_TEST_REGION,
        client=client,
    )


_REAL_ADAPTERS = pytest.mark.parametrize(
    "factory",
    [_fake_factory, _local_factory, _s3_factory],
    ids=["fake", "local", "s3"],
)


@_REAL_ADAPTERS
def test_put_then_get_returns_bytes(factory: AdapterFactory, tmp_path: Path) -> None:
    port = factory(tmp_path)
    put_result = port.put("k1", b"hello", "text/plain")
    assert isinstance(put_result, Ok)
    get_result = port.get("k1")
    assert isinstance(get_result, Ok)
    assert get_result.value == b"hello"


@_REAL_ADAPTERS
def test_get_missing_key_returns_not_found(
    factory: AdapterFactory, tmp_path: Path
) -> None:
    port = factory(tmp_path)
    result = port.get("missing")
    assert isinstance(result, Err)
    assert isinstance(result.error, ObjectNotFoundError)


@_REAL_ADAPTERS
def test_delete_missing_key_is_noop(factory: AdapterFactory, tmp_path: Path) -> None:
    port = factory(tmp_path)
    result = port.delete("never-existed")
    assert isinstance(result, Ok)


@_REAL_ADAPTERS
def test_delete_removes_object(factory: AdapterFactory, tmp_path: Path) -> None:
    port = factory(tmp_path)
    port.put("k1", b"x", "application/octet-stream")
    delete_result = port.delete("k1")
    assert isinstance(delete_result, Ok)
    get_result = port.get("k1")
    assert isinstance(get_result, Err)
    assert isinstance(get_result.error, ObjectNotFoundError)


@_REAL_ADAPTERS
def test_put_overwrites_existing_object(
    factory: AdapterFactory, tmp_path: Path
) -> None:
    port = factory(tmp_path)
    port.put("k1", b"first", "text/plain")
    port.put("k1", b"second", "text/plain")
    get_result = port.get("k1")
    assert isinstance(get_result, Ok)
    assert get_result.value == b"second"


@_REAL_ADAPTERS
def test_signed_url_returns_a_string_for_existing_key(
    factory: AdapterFactory, tmp_path: Path
) -> None:
    port = factory(tmp_path)
    port.put("k1", b"x", "text/plain")
    result = port.signed_url("k1", expires_in=60)
    assert isinstance(result, Ok)
    assert isinstance(result.value, str)
    assert result.value
