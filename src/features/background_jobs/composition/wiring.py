"""Wiring helpers for the background-jobs feature."""

from __future__ import annotations

from fastapi import FastAPI

from features.background_jobs.composition.container import JobsContainer


def attach_jobs_container(app: FastAPI, container: JobsContainer) -> None:
    """Publish the :class:`JobsContainer` on ``app.state``."""
    app.state.jobs_container = container


def get_jobs_container(app: FastAPI) -> JobsContainer:
    """Return the previously-attached :class:`JobsContainer`."""
    container = getattr(app.state, "jobs_container", None)
    if container is None:
        raise RuntimeError("JobsContainer has not been attached to app.state")
    return container
