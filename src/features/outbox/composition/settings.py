"""Per-feature settings view used by the outbox composition root.

The outbox feature reads only a handful of knobs — whether the pattern
is enabled, how often the relay wakes up, how many rows it claims per
tick, the per-row retry budget + backoff shape, and an identifier for
the worker that holds the claim. Owning the projection here keeps the
env-loading boundary (:mod:`app_platform.config.settings`) free of
feature-internal defaults and gives the feature its own
``validate_production`` hook.
"""

from __future__ import annotations

import logging
import os
import socket
from dataclasses import dataclass
from typing import Protocol

_logger = logging.getLogger("features.outbox.settings")


class _OutboxAppSettings(Protocol):
    """Structural view of :class:`AppSettings` the outbox feature reads.

    Declared locally so the outbox feature does not import the platform
    composition root (which would transitively pull in every other
    feature's settings module).
    """

    outbox_enabled: bool
    outbox_relay_interval_seconds: float
    outbox_claim_batch_size: int
    outbox_max_attempts: int
    outbox_retry_base_seconds: float
    outbox_retry_max_seconds: float
    outbox_worker_id: str | None
    outbox_retention_delivered_days: int
    outbox_retention_failed_days: int
    outbox_prune_batch_size: int


def _default_worker_id() -> str:
    """Compute a stable-per-process worker identifier.

    The identifier is recorded in ``outbox_messages.locked_by`` so an
    operator can see *which* worker holds a row mid-flight when
    inspecting the table. Hostname + PID is sufficient: it stays stable
    for the lifetime of a single worker process and changes naturally
    across restarts and replicas.
    """
    return f"{socket.gethostname()}:{os.getpid()}"


@dataclass(frozen=True, slots=True)
class OutboxSettings:
    """Subset of :class:`AppSettings` the outbox feature reads."""

    enabled: bool
    relay_interval_seconds: float
    claim_batch_size: int
    max_attempts: int
    retry_base_seconds: float
    retry_max_seconds: float
    worker_id: str
    retention_delivered_days: int
    retention_failed_days: int
    prune_batch_size: int

    @classmethod
    def from_app_settings(
        cls,
        app: _OutboxAppSettings | None = None,
        *,
        enabled: bool | None = None,
        relay_interval_seconds: float | None = None,
        claim_batch_size: int | None = None,
        max_attempts: int | None = None,
        retry_base_seconds: float | None = None,
        retry_max_seconds: float | None = None,
        worker_id: str | None = None,
        retention_delivered_days: int | None = None,
        retention_failed_days: int | None = None,
        prune_batch_size: int | None = None,
    ) -> OutboxSettings:
        """Construct from either an :class:`AppSettings` or flat kwargs."""
        if app is not None:
            enabled = app.outbox_enabled
            relay_interval_seconds = app.outbox_relay_interval_seconds
            claim_batch_size = app.outbox_claim_batch_size
            max_attempts = app.outbox_max_attempts
            retry_base_seconds = app.outbox_retry_base_seconds
            retry_max_seconds = app.outbox_retry_max_seconds
            worker_id = app.outbox_worker_id
            retention_delivered_days = app.outbox_retention_delivered_days
            retention_failed_days = app.outbox_retention_failed_days
            prune_batch_size = app.outbox_prune_batch_size
        if enabled is None:
            raise ValueError("OutboxSettings: 'enabled' is required")
        return cls(
            enabled=bool(enabled),
            relay_interval_seconds=float(
                5.0 if relay_interval_seconds is None else relay_interval_seconds
            ),
            claim_batch_size=int(100 if claim_batch_size is None else claim_batch_size),
            max_attempts=int(8 if max_attempts is None else max_attempts),
            retry_base_seconds=float(
                30.0 if retry_base_seconds is None else retry_base_seconds
            ),
            retry_max_seconds=float(
                900.0 if retry_max_seconds is None else retry_max_seconds
            ),
            worker_id=worker_id or _default_worker_id(),
            retention_delivered_days=int(
                7 if retention_delivered_days is None else retention_delivered_days
            ),
            retention_failed_days=int(
                30 if retention_failed_days is None else retention_failed_days
            ),
            prune_batch_size=int(
                1000 if prune_batch_size is None else prune_batch_size
            ),
        )

    @property
    def dedup_retention_seconds(self) -> float:
        """Derived dedup-mark retention window.

        Pegged to ``2 * retry_max_seconds`` so by the time a mark would
        be deleted, the corresponding outbox row has already reached a
        terminal state (delivered or failed) and could not be redelivered
        even if the mark vanished. Exposing this as a property keeps the
        knob count down — operators only tune ``retry_max_seconds`` and
        the dedup retention follows automatically.
        """
        return 2.0 * self.retry_max_seconds

    def validate(self, errors: list[str]) -> None:
        if self.relay_interval_seconds <= 0:
            errors.append("APP_OUTBOX_RELAY_INTERVAL_SECONDS must be > 0")
        if self.claim_batch_size <= 0:
            errors.append("APP_OUTBOX_CLAIM_BATCH_SIZE must be > 0")
        if self.max_attempts <= 0:
            errors.append("APP_OUTBOX_MAX_ATTEMPTS must be > 0")
        if self.retry_base_seconds <= 0:
            errors.append("APP_OUTBOX_RETRY_BASE_SECONDS must be > 0")
        if self.retry_max_seconds <= 0:
            errors.append("APP_OUTBOX_RETRY_MAX_SECONDS must be > 0")
        if self.retry_max_seconds < self.retry_base_seconds:
            errors.append(
                "APP_OUTBOX_RETRY_MAX_SECONDS must be >= APP_OUTBOX_RETRY_BASE_SECONDS"
            )
        if self.retention_delivered_days <= 0:
            errors.append("APP_OUTBOX_RETENTION_DELIVERED_DAYS must be > 0")
        if self.retention_failed_days <= 0:
            errors.append("APP_OUTBOX_RETENTION_FAILED_DAYS must be > 0")
        if self.prune_batch_size <= 0:
            errors.append("APP_OUTBOX_PRUNE_BATCH_SIZE must be > 0")
        if (
            self.retention_delivered_days > 0
            and self.retention_failed_days > 0
            and self.retention_failed_days < self.retention_delivered_days
        ):
            # Warning rather than hard error: operators may deliberately
            # configure aggressive failed-row pruning (e.g. when a separate
            # alerting pipeline captures the failure detail elsewhere). The
            # standard ops pattern is the opposite — failures are kept
            # longer than successes — so we surface a hint via the
            # validator output without refusing the configuration.
            _logger.warning(
                "APP_OUTBOX_RETENTION_FAILED_DAYS (%d) < "
                "APP_OUTBOX_RETENTION_DELIVERED_DAYS (%d): failed rows are "
                "operator-actionable evidence and are typically kept "
                "longer than delivered rows.",
                self.retention_failed_days,
                self.retention_delivered_days,
            )

    def validate_production(self, errors: list[str]) -> None:
        if not self.enabled:
            errors.append(
                "APP_OUTBOX_ENABLED must be true in production so the "
                "transactional outbox relay actually runs; without it, "
                "every request that writes to OutboxPort would stall "
                "indefinitely (no relay would claim the rows)."
            )
