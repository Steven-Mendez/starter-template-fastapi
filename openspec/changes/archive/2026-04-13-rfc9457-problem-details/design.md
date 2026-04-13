## Context

FastAPI defaults to JSON error bodies (`{"detail": ...}`) with `application/json`. We centralize error rendering without changing route logic: routes continue to raise `HTTPException`; validation continues to raise `RequestValidationError`.

## Goals

- Use `Content-Type: application/problem+json` for Problem Details responses (RFC 9457 §4).
- Include core members: `type` (URI reference, default `about:blank`), `title`, `status`, and when applicable `detail` and `instance`.
- For validation errors (422), include FastAPI’s structured error list under an extension member `errors` so clients retain field-level information.

## Non-goals

- Changing HTTP status codes or business rules in Kanban routes.
- Content negotiation beyond always emitting Problem Details for handled API errors (no alternate XML profile in this change).

## Implementation notes

- Register `exception_handler` for `HTTPException` and `RequestValidationError` on the `FastAPI` app.
- Set `instance` to the request URL (absolute), which satisfies the “occurrence” URI reference from RFC 9457.
- Use standard HTTP reason phrases for `title` when raising generic status errors; use `HTTPException.detail` as `detail` when it is a string.

## Risks / follow-ups

- OpenAPI response schemas for routes do not automatically list `application/problem+json`; documenting error models globally can be a later improvement.
