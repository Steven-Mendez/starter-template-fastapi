"""Behavioural contract shared by every :class:`FileStoragePort` implementation.

The fake and the local on-disk adapter are exercised against the same
scenarios so a regression on either side surfaces here. The s3 stub
is parametrised in too, but every scenario is marked ``xfail`` until
the stub is implemented — the parametrisation exists so an
implementer cannot silently forget the contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from src.features.file_storage.adapters.outbound.local import LocalFileStorageAdapter
from src.features.file_storage.adapters.outbound.s3 import S3FileStorageAdapter
from src.features.file_storage.application.errors import (
    ObjectNotFoundError,
)
from src.features.file_storage.application.ports.file_storage_port import (
    FileStoragePort,
)
from src.features.file_storage.tests.fakes.fake_file_storage import FakeFileStorage
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


AdapterFactory = Callable[[Path], FileStoragePort]


def _fake_factory(_: Path) -> FileStoragePort:
    return FakeFileStorage()


def _local_factory(tmp_path: Path) -> FileStoragePort:
    return LocalFileStorageAdapter(root=tmp_path / "storage")


def _s3_factory(_: Path) -> FileStoragePort:
    return S3FileStorageAdapter(bucket="contract-test", region="us-east-1")


# The s3 stub raises ``NotImplementedError`` from every method until it
# is implemented. Parametrising it in with ``xfail`` keeps the scenario
# list honest: a real implementation flips ``strict=True`` (or removes
# the marker) and any drift fails immediately.
_REAL_ADAPTERS = pytest.mark.parametrize(
    "factory",
    [_fake_factory, _local_factory],
    ids=["fake", "local"],
)
_ALL_ADAPTERS = pytest.mark.parametrize(
    "factory",
    [
        _fake_factory,
        _local_factory,
        pytest.param(
            _s3_factory,
            marks=pytest.mark.xfail(
                raises=NotImplementedError,
                reason="S3 adapter is a stub; see adapters/outbound/s3/README.md",
                strict=True,
            ),
        ),
    ],
    ids=["fake", "local", "s3"],
)


@_ALL_ADAPTERS
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
