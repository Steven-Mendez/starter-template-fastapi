"""Unit tests for :class:`LocalFileStorageAdapter` specifics.

The cross-adapter behavioural contract lives in
``tests/contracts/test_file_storage_port_contract.py``; this module
covers the local-only details: the sha256 prefix layout, the
``file://`` URL scheme, and the writability check at construction.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app_platform.shared.result import Ok, expect_ok
from features.file_storage.adapters.outbound.local import LocalFileStorageAdapter

pytestmark = pytest.mark.unit


def test_object_path_uses_sha256_two_level_prefix(tmp_path: Path) -> None:
    adapter = LocalFileStorageAdapter(root=tmp_path)
    expect_ok(adapter.put("k1", b"x", "text/plain"))
    digest = hashlib.sha256(b"k1").hexdigest()
    expected = tmp_path / digest[:2] / digest[2:4] / digest
    assert expected.exists()


def test_signed_url_returns_file_uri(tmp_path: Path) -> None:
    adapter = LocalFileStorageAdapter(root=tmp_path)
    expect_ok(adapter.put("k1", b"x", "text/plain"))
    result = adapter.signed_url("k1", expires_in=60)
    assert isinstance(result, Ok)
    assert result.value.startswith("file://")


def test_root_is_created_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "storage"
    assert not target.exists()
    LocalFileStorageAdapter(root=target)
    assert target.is_dir()


def test_constructor_rejects_unwritable_root(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"")
    target = blocker / "storage"
    with pytest.raises(RuntimeError):
        LocalFileStorageAdapter(root=target)
