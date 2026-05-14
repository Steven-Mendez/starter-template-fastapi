"""Background-job registration for the users feature.

Registers the ``delete_user_assets`` handler with the
:class:`JobHandlerRegistry`. The handler is a thin shim: it unpacks
the payload's ``user_id`` and calls the wired
:class:`UserAssetsCleanupPort`. The web process registers it so its
in-process job-queue adapter can reach the handler in tests; the
worker process registers the same handler against the same name so
the relay's at-least-once delivery has a known consumer.

When the handler is invoked through the outbox relay, the payload
carries the reserved key ``__outbox_message_id``. The handler is
at-least-once on the relay side, so a second delivery with the same
id MUST be a no-op. Wiring code passes a ``dedupe`` callable that
records the message id (typically an ``INSERT`` into the outbox
feature's ``processed_outbox_messages`` table) and returns ``False``
if the id was already recorded — in that case the handler skips the
cleanup and returns success. When no ``dedupe`` callable is wired,
the handler runs unconditionally (and relies on
:meth:`UserAssetsCleanupPort.delete_user_assets` being idempotent
on the empty prefix).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from app_platform.shared.result import Err
from features.background_jobs.application.registry import JobHandlerRegistry
from features.users.application.ports.user_assets_cleanup_port import (
    UserAssetsCleanupPort,
)
from features.users.application.use_cases.erase_user import EraseUser

_logger = logging.getLogger("features.users.jobs")

# Job names — mirror the constants on the use cases so enqueue and
# handler-registration stay in agreement. Re-defined here (rather than
# imported) so the composition module stays in the outermost ring.
DELETE_USER_ASSETS_JOB = "delete_user_assets"
ERASE_USER_JOB = "erase_user"

# Reserved payload key the outbox relay injects.
_OUTBOX_MESSAGE_ID_KEY = "__outbox_message_id"

# Returns ``True`` if the message id was newly recorded (the handler
# should proceed to clean up), ``False`` if it was already processed
# (the handler MUST short-circuit to ``Ok`` / no-op).
HandlerDedupe = Callable[[str], bool]


def register_delete_user_assets_handler(
    registry: JobHandlerRegistry,
    cleanup_port: UserAssetsCleanupPort,
    *,
    dedupe: HandlerDedupe | None = None,
) -> None:
    """Register the ``delete_user_assets`` handler on ``registry``.

    Called from ``src/main.py`` and ``src/worker.py``. The web process
    needs the registration so payload validity checks at enqueue time
    line up with what the worker can actually run.
    """

    def _handler(payload: dict[str, Any]) -> None:
        message_id = payload.get(_OUTBOX_MESSAGE_ID_KEY)
        if (
            dedupe is not None
            and isinstance(message_id, str)
            and not dedupe(message_id)
        ):
            _logger.info(
                "event=jobs.delete_user_assets.deduped outbox_message_id=%s",
                message_id,
            )
            return
        raw_user_id = payload["user_id"]
        try:
            user_id = UUID(str(raw_user_id))
        except (TypeError, ValueError) as exc:
            # Bad payload is not retryable. Raise so the worker's retry
            # policy classifies it as a hard failure rather than looping
            # indefinitely on a structurally broken row.
            raise RuntimeError(
                f"delete_user_assets received invalid user_id={raw_user_id!r}"
            ) from exc
        result = cleanup_port.delete_user_assets(user_id)
        if isinstance(result, Err):
            _logger.error(
                "event=jobs.delete_user_assets.failed user_id=%s reason=%s",
                user_id,
                result.error,
            )
            raise RuntimeError(f"delete_user_assets failed: {result.error}")  # noqa: TRY004 — Result-type pattern match, not a type guard

    registry.register_handler(DELETE_USER_ASSETS_JOB, _handler)


def register_erase_user_handler(
    registry: JobHandlerRegistry,
    erase_user: EraseUser,
    *,
    dedupe: HandlerDedupe | None = None,
) -> None:
    """Register the ``erase_user`` handler on ``registry``.

    The handler unpacks ``user_id`` and ``reason`` from the payload and
    calls :meth:`EraseUser.execute`. The use case is idempotent on an
    already-erased user, so the relay's at-least-once redelivery is
    safe even without the optional ``dedupe`` callable; wiring code
    passes one anyway so duplicate cleanup-job enqueues are avoided.
    """

    def _handler(payload: dict[str, Any]) -> None:
        message_id = payload.get(_OUTBOX_MESSAGE_ID_KEY)
        if (
            dedupe is not None
            and isinstance(message_id, str)
            and not dedupe(message_id)
        ):
            _logger.info(
                "event=jobs.erase_user.deduped outbox_message_id=%s",
                message_id,
            )
            return
        raw_user_id = payload["user_id"]
        try:
            user_id = UUID(str(raw_user_id))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"erase_user received invalid user_id={raw_user_id!r}"
            ) from exc
        reason = payload.get("reason", "self_request")
        if reason not in ("self_request", "admin_request"):
            # Defensive: reject unknown reasons rather than recording an
            # audit row with garbage. The producer side controls the
            # value and this is the canary if it ever drifts.
            raise RuntimeError(f"erase_user received unknown reason={reason!r}")
        result = erase_user.execute(user_id, reason)
        if isinstance(result, Err):
            _logger.error(
                "event=jobs.erase_user.failed user_id=%s reason=%s",
                user_id,
                result.error,
            )
            raise RuntimeError(f"erase_user failed: {result.error}")  # noqa: TRY004 — Result-type pattern match, not a type guard

    registry.register_handler(ERASE_USER_JOB, _handler)
