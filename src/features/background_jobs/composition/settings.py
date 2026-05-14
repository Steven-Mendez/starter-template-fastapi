"""Per-feature settings view used by the background-jobs composition root.

Holds only the values the feature reads at startup. Owns its own
production validation: production deployments must use the ``arq``
backend (an in-process queue would lose every queued job on a restart).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

JobsBackend = Literal["in_process", "arq"]


class _JobsAppSettings(Protocol):
    """Structural view of :class:`AppSettings` the jobs feature reads.

    Declared locally so the jobs feature does not import the platform
    composition root (which would transitively pull in every other
    feature's settings module).
    """

    jobs_backend: JobsBackend
    jobs_redis_url: str | None
    auth_redis_url: str | None
    jobs_queue_name: str
    jobs_keep_result_seconds_default: int
    jobs_max_jobs: int
    jobs_job_timeout_seconds: int


@dataclass(frozen=True, slots=True)
class JobsSettings:
    """Subset of :class:`AppSettings` the background-jobs feature reads."""

    backend: JobsBackend
    redis_url: str | None
    queue_name: str
    keep_result_seconds_default: int = 300
    max_jobs: int = 16
    job_timeout_seconds: int = 600

    @classmethod
    def from_app_settings(
        cls,
        app: _JobsAppSettings | None = None,
        *,
        backend: str | None = None,
        redis_url: str | None = None,
        queue_name: str | None = None,
        keep_result_seconds_default: int = 300,
        max_jobs: int = 16,
        job_timeout_seconds: int = 600,
    ) -> JobsSettings:
        """Construct from either an :class:`AppSettings` or flat kwargs."""
        if app is not None:
            backend = app.jobs_backend
            # APP_JOBS_REDIS_URL falls back to APP_AUTH_REDIS_URL so single-Redis
            # deployments don't need both env vars set.
            redis_url = app.jobs_redis_url or app.auth_redis_url
            queue_name = app.jobs_queue_name
            keep_result_seconds_default = app.jobs_keep_result_seconds_default
            max_jobs = app.jobs_max_jobs
            job_timeout_seconds = app.jobs_job_timeout_seconds
        if backend not in ("in_process", "arq"):
            raise ValueError(
                f"APP_JOBS_BACKEND must be 'in_process' or 'arq'; got {backend!r}"
            )
        return cls(
            backend=backend,  # type: ignore[arg-type]
            redis_url=redis_url,
            queue_name=queue_name or "arq:queue",
            keep_result_seconds_default=keep_result_seconds_default,
            max_jobs=max_jobs,
            job_timeout_seconds=job_timeout_seconds,
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
