"""Pluggable error-reporting seam (`ErrorReporterPort`) and shipped adapters.

The platform's unhandled-exception handler routes every otherwise-uncaught
exception through :class:`ErrorReporterPort.capture` so operators get a
paging signal without bolting `sentry_sdk` calls into the request path.

Two adapters ship out of the box:

- :class:`LoggingErrorReporter` — default; emits a structured WARN log
  line and returns. Used when ``APP_SENTRY_DSN`` is unset, and as the
  fallback when the DSN is set but the optional ``sentry`` extra is not
  installed.
- :class:`SentryErrorReporter` — wraps the ``sentry-sdk`` ``capture_exception``
  / ``set_context`` calls. Lives behind the ``sentry`` optional extra; the
  constructor raises :class:`ModuleNotFoundError` when ``sentry_sdk`` is not
  importable so the factory can fall back per the selection rule documented
  in :mod:`app_platform.api.app_factory`.

Both adapters wrap their work in ``try/except Exception`` so a broken
reporter never escalates the request failure — the contract is that
``capture`` MUST NOT raise.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ErrorReporterPort",
    "LoggingErrorReporter",
    "SentryErrorReporter",
]

_logger = logging.getLogger("api.error.reporter")


@runtime_checkable
class ErrorReporterPort(Protocol):
    """Capture an unhandled exception with structured context.

    Implementations MUST NOT raise. A broken reporter must never escalate
    the request failure; on internal error, log and return.

    The ``**context`` keys passed by ``unhandled_exception_handler`` are
    ``request_id``, ``path``, ``method``, and ``principal_id`` (nullable).
    Implementations should preserve unknown keys for forward compatibility.
    """

    def capture(self, exc: BaseException, **context: Any) -> None:
        """Record ``exc`` with the supplied ``context`` keys."""
        ...


class LoggingErrorReporter:
    """Default reporter: emits a structured WARN log and returns.

    Useful as a no-op-equivalent in environments without paging
    (development, internal-only deployments) and as the fallback when the
    Sentry extra is not installed.
    """

    name = "logging"

    def capture(self, exc: BaseException, **context: Any) -> None:
        """Log ``exc`` with the supplied ``context`` keys as ``extra``."""
        try:
            _logger.warning(
                "Unhandled exception captured by LoggingErrorReporter",
                extra={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    **context,
                },
            )
        except Exception:  # pragma: no cover — defensive; reporter MUST NOT raise
            _logger.exception(
                "event=error_reporter.logging.capture_failed",
            )


class SentryErrorReporter:
    """Forward unhandled exceptions to Sentry via ``sentry-sdk``.

    The constructor performs the ``sentry_sdk`` import so callers can rely
    on a clean :class:`ModuleNotFoundError` at construction time (rather
    than at first call). The factory uses this signal to fall back to
    :class:`LoggingErrorReporter` when the optional ``sentry`` extra is
    not installed.

    ``capture`` wraps ``capture_exception`` and ``set_context`` in
    ``try/except Exception`` so a Sentry transport failure cannot
    escalate the original request failure.
    """

    name = "sentry"

    def __init__(self) -> None:
        """Import ``sentry_sdk`` eagerly.

        Raises:
            ModuleNotFoundError: when the ``sentry`` optional extra is
                not installed. The factory catches this and falls back to
                :class:`LoggingErrorReporter`.
        """
        import sentry_sdk

        self._sentry_sdk = sentry_sdk

    def capture(self, exc: BaseException, **context: Any) -> None:
        """Forward ``exc`` and ``context`` to Sentry. Never raises."""
        try:
            if context:
                # ``set_context`` accepts a dict per "namespace"; we use a
                # single ``request`` namespace so all keys land on the
                # same Sentry event tab.
                self._sentry_sdk.set_context("request", dict(context))
            self._sentry_sdk.capture_exception(exc)
        except Exception:
            _logger.exception(
                "event=error_reporter.sentry.capture_failed",
                extra={"error_type": type(exc).__name__},
            )
