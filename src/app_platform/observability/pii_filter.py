"""PII / token redaction for structlog and stdlib logging.

Two seams are exposed:

* :class:`PiiRedactionProcessor` — a structlog processor with the
  ``(logger, method_name, event_dict) -> event_dict`` signature. Walks
  the event dict by key (case-insensitive) and applies the redaction
  policy declared in :mod:`app_platform.observability.redaction`.
* :class:`PiiLogFilter` — a :class:`logging.Filter` that mirrors the
  same key-based policy onto ``record.args`` (when it is a mapping)
  and onto any ``extra=`` attributes promoted onto the record. This is
  the safety net for plain-stdlib log calls (uvicorn, third-party
  libraries) that never reach the structlog chain.

Both implementations are conservative: matching is by exact key name,
case-insensitive. Plain-string positional args are NEVER scanned.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app_platform.observability.redaction import (
    REDACT_EMAIL_KEYS,
    REDACT_HEADER_NAMES,
    REDACT_STRICT_KEYS,
    REDACTED_PLACEHOLDER,
    redact_email,
)

# Logger attributes set by the stdlib that the filter must leave alone.
# Mirror of ``_STANDARD_LOGRECORD_ATTRS`` in :mod:`logging` but kept
# private here to avoid coupling to the formatter module.
_STDLIB_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
        # Stamped by RequestIdFilter — these are not PII.
        "request_id",
        "trace_id",
    }
)

_HEADERS_KEYS = frozenset({"headers", "request.headers", "response.headers"})


def _redact_value_for_key(key: str, value: Any) -> Any:
    """Return ``value`` redacted according to the policy for ``key``.

    ``key`` is matched case-insensitively. Non-string values for
    email keys are left untouched (the policy only knows how to mask
    string-shaped emails). Strict keys are always replaced regardless
    of the value's type.
    """
    lowered = key.lower()
    if lowered in REDACT_STRICT_KEYS:
        return REDACTED_PLACEHOLDER
    if lowered in REDACT_EMAIL_KEYS and isinstance(value, str):
        return redact_email(value)
    return value


def _redact_headers_mapping(headers: Mapping[str, Any]) -> dict[str, Any]:
    """Return a new dict with every header value redacted per policy.

    Applies the header deny-list AND the strict/email rules so a stray
    ``Authorization`` header is masked even if a caller did not add it
    to :data:`REDACT_HEADER_NAMES`.
    """
    redacted: dict[str, Any] = {}
    for header_name, header_value in headers.items():
        lowered = header_name.lower()
        if lowered in REDACT_HEADER_NAMES or lowered in REDACT_STRICT_KEYS:
            redacted[header_name] = REDACTED_PLACEHOLDER
        elif lowered in REDACT_EMAIL_KEYS and isinstance(header_value, str):
            redacted[header_name] = redact_email(header_value)
        else:
            redacted[header_name] = header_value
    return redacted


def _redact_event_dict_in_place(event_dict: dict[str, Any]) -> None:
    """Walk top-level ``event_dict`` keys and rewrite their values.

    Nested ``headers`` mappings receive the header-specific treatment.
    """
    for key in list(event_dict.keys()):
        value = event_dict[key]
        if key in _HEADERS_KEYS or key.lower() in _HEADERS_KEYS:
            if isinstance(value, Mapping):
                event_dict[key] = _redact_headers_mapping(value)
            continue
        event_dict[key] = _redact_value_for_key(key, value)


class PiiRedactionProcessor:
    """structlog processor that redacts PII / token-bearing keys.

    The processor walks the top-level keys of the event dict (matching
    case-insensitively) and applies:

    * :data:`REDACT_STRICT_KEYS` → value replaced with
      ``"***REDACTED***"``.
    * :data:`REDACT_EMAIL_KEYS` → string values passed through
      :func:`redact_email`; non-string values pass through unchanged.
    * Nested ``headers`` / ``request.headers`` / ``response.headers``
      mappings receive the same treatment plus the
      :data:`REDACT_HEADER_NAMES` deny-list.

    Value scanning / regex sweeps over message strings are explicitly
    out of scope.
    """

    def __call__(
        self,
        logger: Any,  # noqa: ARG002 — structlog processor signature
        method_name: str,  # noqa: ARG002 — structlog processor signature
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply the redaction policy to ``event_dict`` in place."""
        _redact_event_dict_in_place(event_dict)
        return event_dict


class PiiLogFilter(logging.Filter):
    """Stdlib :class:`logging.Filter` that mirrors :class:`PiiRedactionProcessor`.

    Mounted on the root logger so plain-stdlib log calls (uvicorn,
    third-party libraries that do not go through structlog) are also
    covered. The filter applies the policy to:

    * ``record.args`` when it is a :class:`collections.abc.Mapping`
      (i.e. dict-style ``%(name)s`` formatting).
    * Any non-stdlib attribute promoted onto the record via
      ``extra={...}`` (matched against :data:`_STDLIB_RECORD_ATTRS`).

    Plain-string positional args are NOT scanned — value scanning is
    out of scope, both for cost and for legibility of the redaction
    rules. Call-site redaction (e.g. ``to=redact_email(to)``) is the
    intended approach for string-shaped log calls.

    The filter always returns ``True`` so it never drops records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact PII / token fields on ``record`` in place."""
        # Mapping-style %(name)s formatting: rewrite the args dict.
        if isinstance(record.args, Mapping):
            redacted_args: dict[str, Any] = {}
            for key, value in record.args.items():
                key_str = str(key)
                lowered = key_str.lower()
                if lowered in _HEADERS_KEYS and isinstance(value, Mapping):
                    redacted_args[key_str] = _redact_headers_mapping(value)
                else:
                    redacted_args[key_str] = _redact_value_for_key(key_str, value)
            record.args = redacted_args

        # ``extra={...}`` keys are promoted onto the record as attributes.
        # Walk record.__dict__, skipping the stdlib's standard attributes
        # plus dunders (e.g. ``__class__``) that are not user-supplied.
        for attr_name in list(record.__dict__.keys()):
            if attr_name in _STDLIB_RECORD_ATTRS or attr_name.startswith("_"):
                continue
            value = record.__dict__[attr_name]
            lowered = attr_name.lower()
            if lowered in _HEADERS_KEYS and isinstance(value, Mapping):
                record.__dict__[attr_name] = _redact_headers_mapping(value)
            else:
                record.__dict__[attr_name] = _redact_value_for_key(attr_name, value)

        return True
