"""Prometheus metrics setup.

Mounts ``/metrics`` with standard RED (Rate, Errors, Duration) metrics via
``prometheus-fastapi-instrumentator``, plus custom application counters.

Usage::

    from src.platform.observability.metrics import configure_metrics
    configure_metrics(app, settings)

Custom counters are registered as module-level singletons so feature code
can import and increment them directly::

    from src.platform.observability.metrics import (
        AUTH_LOGIN_ATTEMPTS,
        AUTH_RATE_LIMIT_BLOCKS,
        KANBAN_CARD_MOVES,
    )
    AUTH_LOGIN_ATTEMPTS.labels(outcome="success").inc()
"""

from __future__ import annotations

import logging

from prometheus_client import Counter

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom application counters
# ---------------------------------------------------------------------------

AUTH_LOGIN_ATTEMPTS: Counter = Counter(
    "auth_login_attempts_total",
    "Total login attempts, labelled by outcome (success / failure)",
    ["outcome"],
)

AUTH_RATE_LIMIT_BLOCKS: Counter = Counter(
    "auth_rate_limit_blocks_total",
    "Total requests blocked by the auth rate limiter",
    ["endpoint"],
)

KANBAN_CARD_MOVES: Counter = Counter(
    "kanban_card_moves_total",
    "Total card move operations",
)


def configure_metrics(app: object, *, enabled: bool = True) -> None:
    """Mount the ``/metrics`` Prometheus endpoint on ``app``.

    When ``enabled`` is ``False`` (e.g. in tests) the instrumentator is still
    initialised so imports of the custom counters work, but the endpoint is
    not mounted.

    Args:
        app: The FastAPI application instance.
        enabled: Whether to mount and expose the ``/metrics`` endpoint.
    """
    from fastapi import FastAPI
    from prometheus_fastapi_instrumentator import Instrumentator

    if not isinstance(app, FastAPI):
        return

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health/live", "/health/ready", "/health"],
    ).instrument(app)

    if enabled:
        instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)
        _logger.info("event=metrics.enabled endpoint=/metrics")
    else:
        _logger.info(
            "event=metrics.disabled "
            "message=Set APP_METRICS_ENABLED=true to expose /metrics"
        )
