"""Canonical Problem Details ``type`` URN catalog.

RFC 9457 §3.1 recommends ``about:blank`` *only* when no specific problem
type exists. This module defines a stable URN catalog
(:class:`ProblemType`) so SDKs can branch on ``response.json()["type"]``
rather than parse the human-readable ``detail`` string.

The URN scheme is::

    urn:problem:<domain>:<code>

where ``<domain>`` is a lower-kebab capability tag (``auth``, ``authz``,
``validation``, ``generic``) and ``<code>`` is a lower-kebab error slug.
URN values are stable across versions: members may be **added** but
never renamed. ``ProblemType.ABOUT_BLANK`` is the spec-compliant fallback
for genuinely uncategorized errors.

The enum inherits :class:`str` (via :class:`enum.StrEnum`) so members are
drop-in replacements anywhere ``problem_json_response`` or
:class:`ApplicationHTTPException` expects a ``type_uri: str``.
"""

from __future__ import annotations

from enum import StrEnum


class ProblemType(StrEnum):
    """Canonical URN catalog for the Problem Details ``type`` field.

    Values follow the ``urn:problem:<domain>:<code>`` scheme. See the
    module docstring and ``docs/api.md`` for the full reference.
    """

    AUTH_INVALID_CREDENTIALS = "urn:problem:auth:invalid-credentials"
    AUTH_RATE_LIMITED = "urn:problem:auth:rate-limited"
    AUTH_TOKEN_STALE = "urn:problem:auth:token-stale"  # noqa: S105 — URN slug
    AUTH_TOKEN_INVALID = "urn:problem:auth:token-invalid"  # noqa: S105 — URN slug
    AUTH_EMAIL_NOT_VERIFIED = "urn:problem:auth:email-not-verified"
    AUTHZ_PERMISSION_DENIED = "urn:problem:authz:permission-denied"
    VALIDATION_FAILED = "urn:problem:validation:failed"
    GENERIC_CONFLICT = "urn:problem:generic:conflict"
    GENERIC_NOT_FOUND = "urn:problem:generic:not-found"
    ABOUT_BLANK = "about:blank"
