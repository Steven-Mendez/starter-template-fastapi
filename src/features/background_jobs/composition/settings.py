"""Per-feature settings view used by the background-jobs composition root.

Holds only the values the feature reads at startup. Owns its own
production validation: production deployments may not run the
``in_process`` queue (it would lose every queued job on a restart).
``in_process`` is currently the only backend — there is no production
job runtime until the AWS SQS adapter and a Lambda worker are added at
a later roadmap step (``arq`` was removed in ROADMAP ETAPA I step 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

JobsBackend = Literal["in_process"]


class _JobsAppSettings(Protocol):
    """Structural view of :class:`AppSettings` the jobs feature reads.

    Declared locally so the jobs feature does not import the platform
    composition root (which would transitively pull in every other
    feature's settings module).
    """

    jobs_backend: JobsBackend


@dataclass(frozen=True, slots=True)
class JobsSettings:
    """Subset of :class:`AppSettings` the background-jobs feature reads."""

    backend: JobsBackend

    @classmethod
    def from_app_settings(
        cls,
        app: _JobsAppSettings | None = None,
        *,
        backend: str | None = None,
    ) -> JobsSettings:
        """Construct from either an :class:`AppSettings` or flat kwargs."""
        if app is not None:
            backend = app.jobs_backend
        if backend not in ("in_process",):
            raise ValueError(f"APP_JOBS_BACKEND must be 'in_process'; got {backend!r}")
        return cls(backend=backend)  # type: ignore[arg-type]

    def validate(self, errors: list[str]) -> None:
        """Append always-on (non-production-only) validation errors.

        ``in_process`` is the only backend and carries no further
        configuration, so there is nothing to validate here; the
        production rejection lives in :meth:`validate_production`.
        """

    def validate_production(self, errors: list[str]) -> None:
        if self.backend == "in_process":
            errors.append(
                "APP_JOBS_BACKEND must not be 'in_process' in production; "
                "no production job backend is available yet (the AWS SQS "
                "adapter and a Lambda worker arrive at a later roadmap step)"
            )
