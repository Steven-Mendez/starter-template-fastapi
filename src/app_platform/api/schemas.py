"""Pydantic models for OpenAPI declarations of platform-level responses.

This module exposes :class:`ProblemDetails` and :class:`Violation` —
the public, declared shapes of every RFC 9457 error response the
service emits. Runtime serialisation still happens through
:func:`app_platform.api.error_handlers.problem_json_response`; these
models exist so FastAPI can include the schemas in
``components.schemas`` of the generated OpenAPI document and so SDK
generators (openapi-typescript, openapi-python-client, …) can emit
typed error branches.

Keep the field set on these models aligned with the runtime payload
produced by :func:`problem_json_response` and
:func:`pydantic_errors_to_violations`. New extension members SHOULD be
modelled as optional fields here so SDK consumers see them in the
generated types.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Violation(BaseModel):
    """One field-level validation failure on a 422 Problem Details body.

    Mirrors the runtime shape produced by
    :func:`pydantic_errors_to_violations`. The ``input`` field is
    environment-gated at the producer (omitted in production); declaring
    it as optional here documents that contract for SDK consumers.
    """

    loc: list[str | int] = Field(
        ...,
        description=(
            "Canonical Pydantic location path for the failed field, "
            "preserving order and types "
            '(e.g. ``["body", "address", "zip"]``).'
        ),
    )
    type: str = Field(
        ...,
        description=(
            "Stable Pydantic error type "
            "(e.g. ``missing``, ``value_error``, ``string_too_short``)."
        ),
    )
    msg: str = Field(..., description="Human-readable explanation.")
    input: object | None = Field(
        default=None,
        description=(
            "The offending input value. Present only in non-production "
            "environments — omitted entirely when "
            "``APP_ENVIRONMENT=production`` to avoid echoing secrets."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "loc": ["body", "email"],
                "type": "value_error",
                "msg": "value is not a valid email address",
                "input": "not-an-email",
            }
        }
    }


class ProblemDetails(BaseModel):
    """RFC 9457 ``application/problem+json`` body.

    The ``type`` field carries a stable URN drawn from
    :class:`app_platform.api.problem_types.ProblemType` (or
    ``about:blank`` for genuinely uncategorized errors). See
    ``docs/api.md`` for the full URN catalog and the documented
    extension members (``request_id``, ``code``, ``violations``).
    """

    type: str = Field(
        ...,
        description=(
            "Stable Problem Type URN drawn from ``ProblemType`` "
            "(e.g. ``urn:problem:auth:invalid-credentials``) or "
            "``about:blank`` for genuinely uncategorized errors."
        ),
    )
    title: str = Field(
        ...,
        description="HTTP status phrase or explicit validation title.",
    )
    status: int = Field(..., description="HTTP status code.")
    detail: str | None = Field(
        default=None,
        description="Human-readable explanation of this specific occurrence.",
    )
    instance: str | None = Field(
        default=None,
        description="Request URL the error occurred against.",
    )
    violations: list[Violation] | None = Field(
        default=None,
        description=(
            "Field-level validation failures. Present on 422 responses "
            "produced by ``RequestValidationError``; absent otherwise."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "type": "urn:problem:validation:failed",
                "title": "Unprocessable Content",
                "status": 422,
                "detail": "Validation failed: 1 field(s)",
                "instance": "http://localhost:8000/me",
                "violations": [
                    {
                        "loc": ["body", "email"],
                        "type": "value_error",
                        "msg": "value is not a valid email address",
                        "input": "not-an-email",
                    }
                ],
            }
        }
    }
