"""Unit tests for arq worker tunables (max_jobs / job_timeout / keep_result).

Asserts that:
- `WorkerSettings` reflects the configured `max_jobs` and `job_timeout`.
- A handler registered with an explicit `keep_result_seconds` materialises
  into an arq :class:`Function` whose `keep_result` matches.
- A handler registered without override falls back to the registry-wide
  default.
"""

from __future__ import annotations

import pytest

from features.background_jobs.adapters.outbound.arq.worker import build_arq_functions
from features.background_jobs.application.registry import JobHandlerRegistry
from features.background_jobs.composition.settings import JobsSettings

pytestmark = pytest.mark.unit


def test_per_handler_keep_result_overrides_default() -> None:
    registry = JobHandlerRegistry()
    registry.register_handler(
        "send_email",
        lambda payload: None,
        keep_result_seconds=7200,
    )
    registry.seal()

    functions = build_arq_functions(registry, keep_result_seconds_default=300)

    by_name = {f.name: f for f in functions}
    assert by_name["send_email"].keep_result_s == 7200


def test_default_keep_result_applied_when_unset() -> None:
    registry = JobHandlerRegistry()
    registry.register_handler("send_email", lambda payload: None)
    registry.seal()

    functions = build_arq_functions(registry, keep_result_seconds_default=300)

    by_name = {f.name: f for f in functions}
    assert by_name["send_email"].keep_result_s == 300


def test_jobs_settings_exposes_worker_tunables() -> None:
    settings = JobsSettings.from_app_settings(
        backend="arq",
        redis_url="redis://localhost:6379/0",
        queue_name="arq:queue",
        keep_result_seconds_default=900,
        max_jobs=32,
        job_timeout_seconds=1200,
    )
    assert settings.max_jobs == 32
    assert settings.job_timeout_seconds == 1200
    assert settings.keep_result_seconds_default == 900
