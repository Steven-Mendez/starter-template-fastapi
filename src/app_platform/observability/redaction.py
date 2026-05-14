"""Redaction primitives shared by the structlog processor and stdlib filter.

This module deliberately holds no logging dependencies: it exposes a
single :func:`redact_email` helper and three :class:`frozenset` constants
that drive the redaction policy.

The constants are intentionally explicit and closed: matching is by
exact key name (case-insensitive), never by value scanning. See
``openspec/changes/redact-pii-and-tokens-in-logs/design.md`` for the
trade-offs.
"""

from __future__ import annotations

# Keys whose values are always replaced with ``REDACTED_PLACEHOLDER``.
REDACT_STRICT_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "password_hash",
        "hash",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "set-cookie",
        "secret",
        "api_key",
        "phone",
    }
)

# Keys whose string values are masked through :func:`redact_email`.
REDACT_EMAIL_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "to",
        "from",
        "recipient",
        "cc",
        "bcc",
    }
)

# Header names redacted (case-insensitive) when an event dict carries a
# ``headers`` / ``request.headers`` / ``response.headers`` mapping.
REDACT_HEADER_NAMES: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        "x-api-key",
        "x-auth-token",
    }
)

REDACTED_PLACEHOLDER = "***REDACTED***"
_SAFE_EMAIL_FALLBACK = "***@***"


def redact_email(addr: str) -> str:
    """Mask the local part of ``addr`` while preserving the domain.

    Returns strings in the form ``f***@example.com`` — the first
    character of the local part is kept so operators can match against
    the user they expect, and the domain stays intact for diagnostics.

    Edge cases:
    - Inputs without ``@``, with an empty local part, or with an empty
      domain are coerced to ``"***@***"`` rather than echoing the input.
    - Non-string inputs return ``"***@***"`` (the caller is expected to
      pass a string; this is a defensive fallback only).
    """
    if not isinstance(addr, str):
        return _SAFE_EMAIL_FALLBACK
    if "@" not in addr:
        return _SAFE_EMAIL_FALLBACK
    local, _, domain = addr.partition("@")
    if not local or not domain:
        return _SAFE_EMAIL_FALLBACK
    return f"{local[0]}***@{domain}"
