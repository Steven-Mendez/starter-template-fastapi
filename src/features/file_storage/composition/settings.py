"""Per-feature settings view used by the file-storage composition root.

Holds the values the feature reads at startup. Owns its own production
validation: in production a local-filesystem backend is only refused
when a consumer feature has actually wired the port (``storage_enabled``
toggle), so projects that never use file storage can ignore the setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

StorageBackend = Literal["local", "s3"]


@dataclass(frozen=True, slots=True)
class StorageSettings:
    """Subset of :class:`AppSettings` the file-storage feature reads."""

    enabled: bool
    backend: StorageBackend
    local_path: str | None
    s3_bucket: str | None
    s3_region: str

    @classmethod
    def from_app_settings(
        cls,
        app: Any = None,
        *,
        enabled: bool | None = None,
        backend: str | None = None,
        local_path: str | None = None,
        s3_bucket: str | None = None,
        s3_region: str | None = None,
    ) -> "StorageSettings":
        """Construct from either an :class:`AppSettings` or flat kwargs."""
        if app is not None:
            enabled = app.storage_enabled
            backend = app.storage_backend
            local_path = app.storage_local_path
            s3_bucket = app.storage_s3_bucket
            s3_region = app.storage_s3_region
        if backend not in ("local", "s3"):
            raise ValueError(
                f"APP_STORAGE_BACKEND must be 'local' or 's3'; got {backend!r}"
            )
        return cls(
            enabled=bool(enabled),
            backend=backend,  # type: ignore[arg-type]
            local_path=local_path,
            s3_bucket=s3_bucket,
            s3_region=s3_region or "us-east-1",
        )

    def validate(self, errors: list[str]) -> None:
        if self.enabled:
            if self.backend == "local" and not self.local_path:
                errors.append(
                    "APP_STORAGE_BACKEND=local requires APP_STORAGE_LOCAL_PATH"
                )
            if self.backend == "s3" and not self.s3_bucket:
                errors.append("APP_STORAGE_BACKEND=s3 requires APP_STORAGE_S3_BUCKET")

    def validate_production(self, errors: list[str]) -> None:
        if self.enabled and self.backend == "local":
            errors.append(
                "APP_STORAGE_BACKEND must not be 'local' in production when "
                "APP_STORAGE_ENABLED=true; configure 's3' and set "
                "APP_STORAGE_S3_BUCKET"
            )
