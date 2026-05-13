"""Unit tests for :class:`StorageSettings` construction guards."""

from __future__ import annotations

import pytest

from features.file_storage.composition.container import (
    build_file_storage_container,
)
from features.file_storage.composition.settings import StorageSettings

pytestmark = pytest.mark.unit


def test_unknown_backend_rejected() -> None:
    with pytest.raises(ValueError, match="APP_STORAGE_BACKEND"):
        StorageSettings.from_app_settings(
            backend="gcs",
            local_path=None,
            s3_bucket=None,
            s3_region="us-east-1",
        )


def test_local_backend_requires_path() -> None:
    settings = StorageSettings.from_app_settings(
        backend="local",
        local_path=None,
        s3_bucket=None,
        s3_region="us-east-1",
    )
    with pytest.raises(RuntimeError, match="APP_STORAGE_LOCAL_PATH"):
        build_file_storage_container(settings)


def test_s3_backend_requires_bucket() -> None:
    settings = StorageSettings.from_app_settings(
        backend="s3",
        local_path=None,
        s3_bucket=None,
        s3_region="us-east-1",
    )
    with pytest.raises(RuntimeError, match="APP_STORAGE_S3_BUCKET"):
        build_file_storage_container(settings)
