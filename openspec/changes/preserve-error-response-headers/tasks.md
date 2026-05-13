## 1. Merge headers in the generic handler

- [ ] 1.1 In `http_exception_handler` (and every sibling handler in `src/app_platform/api/error_handlers.py`), pass `headers=getattr(exc, "headers", None)` to `JSONResponse(...)`.
- [ ] 1.2 Confirm the handler does not strip headers added by upstream middleware (`X-Request-ID` from `RequestContextMiddleware`, `Content-Language` if set).

## 2. Retry-After on 429

- [ ] 2.1 Update `RateLimitExceededError` in `src/features/authentication/application/errors.py:72`:
  - [ ] 2.1.a Replace the empty body with `__init__(self, message: str, retry_after_seconds: int)` that calls `super().__init__(message)` and stores `self.retry_after_seconds = retry_after_seconds`.
  - [ ] 2.1.b Implement `__reduce__(self)` returning `(type(self), (self.args[0], self.retry_after_seconds))` so the pickling contract from `align-error-class-hierarchy` is satisfied across the arq Redis boundary.
- [ ] 2.2 Compute `retry_after_seconds` from the limiter's window in `src/features/authentication/application/rate_limit.py`:
  - [ ] 2.2.a At `FixedWindowRateLimiter` raise site (line 87), pass `retry_after_seconds=int(self.window_seconds)`.
  - [ ] 2.2.b At `RedisRateLimiter` raise site (line 193), pass `retry_after_seconds=int(self._window_ms // 1000)` (or equivalent positive-integer expression).
- [ ] 2.3 In `src/features/authentication/adapters/inbound/http/errors.py:119`, when `raise_http_from_auth_error` matches `RateLimitExceededError`, set `headers={"Retry-After": str(err.retry_after_seconds)}` on the resulting `HTTPException`.

## 3. Tests

- [ ] 3.1 Add a test that hits an authenticated route without an `Authorization` header and asserts the 401 response includes `WWW-Authenticate: Bearer`.
- [ ] 3.2 Add a test that trips the login rate limit and asserts the 429 response includes a `Retry-After` header parsing as a positive integer.
- [ ] 3.3 Add a test that asserts the 401 response also includes the `X-Request-ID` header set by `RequestContextMiddleware`.
- [ ] 3.4 Add a test that asserts a 4xx response with `Content-Language` set upstream survives the handler.

## 4. Wrap-up

- [ ] 4.1 Run `make ci` and confirm green.
