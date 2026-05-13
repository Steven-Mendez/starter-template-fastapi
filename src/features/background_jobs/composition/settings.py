"""Per-feature settings view used by the background-jobs composition root.

Holds only the values the feature reads at startup. Owns its own
production validation: production deployments must use the ``arq``
backend (an in-process queue would lose every queued job on a restart).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

JobsBackend = Literal["in_process", "arq"]


@dataclass(frozen=True, slots=True)
class JobsSettings:
    """Subset of :class:`AppSettings` the background-jobs feature reads."""

    backend: JobsBackend
    redis_url: str | None
    queue_name: str

    @classmethod
    def from_app_settings(
        cls,
        app: Any = None,
        *,
        backend: str | None = None,
        redis_url: str | None = None,
        queue_name: str | None = None,
    ) -> JobsSettings:
        """Construct from either an :class:`AppSettings` or flat kwargs."""
        if app is not None:
            backend = app.jobs_backend
            # APP_JOBS_REDIS_URL falls back to APP_AUTH_REDIS_URL so single-Redis
            # deployments don't need both env vars set.
            redis_url = app.jobs_redis_url or app.auth_redis_url
            queue_name = app.jobs_queue_name
        if backend not in ("in_process", "arq"):
            raise ValueError(
                f"APP_JOBS_BACKEND must be 'in_process' or 'arq'; got {backend!r}"
            )
        return cls(
            backend=backend,  # type: ignore[arg-type]
            redis_url=redis_url,
            queue_name=queue_name or "arq:queue",
        )

    def validate(self, errors: list[str]) -> None:
        if self.backend == "arq" and not self.redis_url:
            errors.append(
                "APP_JOBS_BACKEND=arq requires APP_JOBS_REDIS_URL "
                "(or APP_AUTH_REDIS_URL) to be set"
            )

    def validate_production(self, errors: list[str]) -> None:
        if self.backend == "in_process":
            errors.append(
                "APP_JOBS_BACKEND must not be 'in_process' in production; "
                "configure 'arq' and set APP_JOBS_REDIS_URL"
            )
