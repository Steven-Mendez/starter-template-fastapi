## Depends on

- `align-error-class-hierarchy` (the new `RateLimitExceededError` field hangs off the canonical taxonomy).
- `add-stable-problem-types` (the 401/429 responses set `type` via `ProblemType`).
- `enrich-validation-error-payload` (header merging coexists with the `violations` body).
- `declare-error-responses-in-openapi` (the documented 401/429 responses model the `WWW-Authenticate` / `Retry-After` headers).

## Conflicts with

Same-file overlap on `src/app_platform/api/error_handlers.py` with `align-error-class-hierarchy`, `add-stable-problem-types`, `enrich-validation-error-payload`, `declare-error-responses-in-openapi`, `add-error-reporting-seam`. Agreed merge order for the chain places this change last so it can layer on the final response shape.

Same-file overlap on `src/features/authentication/adapters/inbound/http/errors.py` with `align-error-class-hierarchy` and `add-stable-problem-types`.

Coordinates with `harden-rate-limiting` (out of cluster) on the rate-limit dependency: this change adds `retry_after_seconds` to `RateLimitExceededError`; `harden-rate-limiting` introduces the per-account limiter that computes the value.

## Context

`HTTPException.headers` exists for a reason; FastAPI/Starlette already plumb it through. The custom handler bypassed it. The fix is one line; the tests are what keep it from regressing.

## Decisions

- **Allow-listed headers that survive an error response**: `X-Request-ID`, `WWW-Authenticate`, `Retry-After`, `Content-Language`. Rationale:
  - `X-Request-ID` — set by `RequestContextMiddleware`; clients use it for support tickets.
  - `WWW-Authenticate` — RFC 7235 challenge on 401; required for spec-compliant Bearer flow.
  - `Retry-After` — RFC 7231 §7.1.3 on 429 / 503; lets polite clients back off correctly.
  - `Content-Language` — propagates the negotiated language for the Problem Details body.
- **Mechanism**: in `http_exception_handler` and sibling handlers in `error_handlers.py`, pass `headers=getattr(exc, "headers", None)` to `JSONResponse(...)`. `X-Request-ID` and `Content-Language` are added by upstream middleware that runs *after* the handler returns, so they survive automatically once the body is rendered; the explicit merge ensures `WWW-Authenticate` and `Retry-After` (set by route code on `HTTPException.headers`) are not dropped.
- **Compute `retry_after_seconds` in the rate-limit dependency, not the HTTP handler**: rationale: the limiter knows the window; the handler doesn't have access to it. The HTTP error mapping reads it off `RateLimitExceededError.retry_after_seconds` and sets the `Retry-After` header on the raised `HTTPException`.

## Risks / Trade-offs

- **Risk**: a header we set that an upstream proxy strips. Out of our control.
- **Risk**: handler accidentally merges a header that leaks server internals (e.g. `Server`, `X-Powered-By`). Mitigation: the allow-list is enforced at the test layer (task 3.x).

## Migration

Single PR. Backwards compatible.
