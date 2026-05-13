## Why

Two related header-handling defects:

1. `http_exception_handler` in `src/app_platform/api/error_handlers.py` constructs a fresh `JSONResponse` without copying `exc.headers`. `raise_http_from_auth_error` sets `WWW-Authenticate: Bearer` on 401s (`src/features/authentication/adapters/inbound/http/errors.py`) — silently dropped before reaching the client, breaking spec-compliant Bearer challenge.
2. `RateLimitExceededError` becomes a bare 429 with no `Retry-After`. Polite clients can't back off correctly; aggressive ones retry tight.

## What Changes

- In `http_exception_handler`, merge `exc.headers` into the response (`headers=getattr(exc, "headers", None) or {}`).
- Add `retry_after_seconds: int` to `RateLimitExceededError`; the rate-limit dependency computes it from the limiter's window and passes it through. The HTTP error mapping sets `Retry-After: <seconds>` on the raised `HTTPException`.
- Enumerate the headers that survive an error response: `X-Request-ID`, `WWW-Authenticate`, `Retry-After`, `Content-Language`.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code (edit)**:
  - `src/app_platform/api/error_handlers.py` (`http_exception_handler` + sibling handlers merge `exc.headers`).
  - `src/features/authentication/application/errors.py` (add `retry_after_seconds: int` to `RateLimitExceededError`).
  - `src/features/authentication/application/rate_limit.py` (compute `retry_after_seconds` from the limiter window when raising `RateLimitExceededError`).
  - `src/features/authentication/adapters/inbound/http/errors.py` (`raise_http_from_auth_error` sets `headers={"Retry-After": str(err.retry_after_seconds)}` when mapping the rate-limit error).
- **Tests**:
  - 401 responses include `WWW-Authenticate: Bearer`.
  - 429 responses include `Retry-After: N` (positive integer).
  - `X-Request-ID` and `Content-Language` survive on error responses.
