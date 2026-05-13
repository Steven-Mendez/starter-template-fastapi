## ADDED Requirements

### Requirement: Error responses preserve their HTTP headers

The generic `http_exception_handler` SHALL merge `exc.headers` into the outgoing `JSONResponse`. The following headers SHALL survive on every error response:

- `X-Request-ID` — set by `RequestContextMiddleware`.
- `WWW-Authenticate` — set by authentication routes on 401 responses (RFC 7235).
- `Retry-After` — set on 429 responses (RFC 7231 §7.1.3) and any other response whose mapping supplies it.
- `Content-Language` — propagated when set by upstream middleware.

#### Scenario: 401 carries Bearer challenge

- **GIVEN** a JWT-protected endpoint
- **WHEN** a request without an `Authorization` header reaches it
- **THEN** the 401 response includes `WWW-Authenticate: Bearer`

#### Scenario: 401 carries the request ID

- **GIVEN** a JWT-protected endpoint
- **WHEN** a request without an `Authorization` header reaches it
- **THEN** the 401 response includes a non-empty `X-Request-ID` header

#### Scenario: 429 carries Retry-After

- **GIVEN** the login rate limit is enabled
- **WHEN** a client trips the per-IP login rate limit
- **THEN** the 429 response includes `Retry-After: N`
- **AND** `N` parses as an integer with `N > 0`

### Requirement: `RateLimitExceededError` carries a retry budget

`RateLimitExceededError` SHALL expose a `retry_after_seconds: int` field, computed by the rate-limit dependency from the limiter's window. The auth HTTP error mapping SHALL set the `Retry-After` header on the resulting `HTTPException` to that value.

#### Scenario: Error carries a positive retry budget

- **GIVEN** a limiter with a 60-second window
- **WHEN** the limiter raises `RateLimitExceededError`
- **THEN** the error instance has `retry_after_seconds > 0`
- **AND** `retry_after_seconds <= 60`
