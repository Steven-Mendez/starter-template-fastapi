"""Application-layer errors for the background-jobs feature."""

from __future__ import annotations

from dataclasses import dataclass


class JobError(Exception):
    """Base class for background-jobs-feature errors."""


@dataclass(frozen=True, slots=True)
class UnknownJobError(JobError):
    """Raised when a caller enqueues a job whose name was never registered.

    Surfaces typos at the call site rather than silently dropping the
    payload onto the queue where the worker would also reject it.
    """

    job_name: str

    def __str__(self) -> str:
        return f"Unknown background job: {self.job_name!r}"


@dataclass(frozen=True, slots=True)
class HandlerAlreadyRegisteredError(JobError):
    """Raised when two features try to register the same job name."""

    job_name: str

    def __str__(self) -> str:
        return f"Background job handler {self.job_name!r} is already registered"
