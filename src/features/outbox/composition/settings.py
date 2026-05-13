"""Per-feature settings view used by the outbox composition root.

The outbox feature reads only a handful of knobs — whether the pattern
is enabled, how often the relay wakes up, how many rows it claims per
tick, the per-row retry budget, and an identifier for the worker that
holds the claim. Owning the projection here keeps the env-loading
boundary (:mod:`src.platform.config.settings`) free of feature-internal
defaults and gives the feature its own ``validate_production`` hook.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from typing import Any


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
    worker_id: str

    @classmethod
    def from_app_settings(
        cls,
        app: Any = None,
        *,
        enabled: bool | None = None,
        relay_interval_seconds: float | None = None,
        claim_batch_size: int | None = None,
        max_attempts: int | None = None,
        worker_id: str | None = None,
    ) -> "OutboxSettings":
        """Construct from either an :class:`AppSettings` or flat kwargs."""
        if app is not None:
            enabled = app.outbox_enabled
            relay_interval_seconds = app.outbox_relay_interval_seconds
            claim_batch_size = app.outbox_claim_batch_size
            max_attempts = app.outbox_max_attempts
            worker_id = app.outbox_worker_id
        if enabled is None:
            raise ValueError("OutboxSettings: 'enabled' is required")
        return cls(
            enabled=bool(enabled),
            relay_interval_seconds=float(
                5.0 if relay_interval_seconds is None else relay_interval_seconds
            ),
            claim_batch_size=int(100 if claim_batch_size is None else claim_batch_size),
            max_attempts=int(8 if max_attempts is None else max_attempts),
            worker_id=worker_id or _default_worker_id(),
        )

    def validate(self, errors: list[str]) -> None:
        if self.relay_interval_seconds <= 0:
            errors.append("APP_OUTBOX_RELAY_INTERVAL_SECONDS must be > 0")
        if self.claim_batch_size <= 0:
            errors.append("APP_OUTBOX_CLAIM_BATCH_SIZE must be > 0")
        if self.max_attempts <= 0:
            errors.append("APP_OUTBOX_MAX_ATTEMPTS must be > 0")

    def validate_production(self, errors: list[str]) -> None:
        if not self.enabled:
            errors.append(
                "APP_OUTBOX_ENABLED must be true in production so the "
                "transactional outbox relay actually runs; without it, "
                "every request that writes to OutboxPort would stall "
                "indefinitely (no relay would claim the rows)."
            )
