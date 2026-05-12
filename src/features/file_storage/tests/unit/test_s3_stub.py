"""Tests for the S3 stub adapter.

The stub raises :class:`NotImplementedError` from every method until
a consumer fills it in. These tests pin that contract: each method
exists, takes the documented arguments, and raises with a hint at
the README.
"""

from __future__ import annotations

import pytest

from src.features.file_storage.adapters.outbound.s3 import S3FileStorageAdapter

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> S3FileStorageAdapter:
    return S3FileStorageAdapter(bucket="b", region="us-east-1")


def test_put_raises_not_implemented(adapter: S3FileStorageAdapter) -> None:
    with pytest.raises(NotImplementedError, match="README"):
        adapter.put("k", b"x", "text/plain")


def test_get_raises_not_implemented(adapter: S3FileStorageAdapter) -> None:
    with pytest.raises(NotImplementedError, match="README"):
        adapter.get("k")


def test_delete_raises_not_implemented(adapter: S3FileStorageAdapter) -> None:
    with pytest.raises(NotImplementedError, match="README"):
        adapter.delete("k")


def test_signed_url_raises_not_implemented(adapter: S3FileStorageAdapter) -> None:
    with pytest.raises(NotImplementedError, match="README"):
        adapter.signed_url("k", expires_in=60)
