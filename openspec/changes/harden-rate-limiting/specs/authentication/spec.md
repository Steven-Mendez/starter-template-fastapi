## MODIFIED Requirements

### Requirement: Auth rate limiter keys on the real client IP

The application SHALL install a proxy-headers middleware configured from `APP_TRUSTED_PROXY_IPS` and rewrite `request.client.host` to the originating client IP before the rate-limit dependency runs. The production validator MUST refuse to start when `APP_ENVIRONMENT=production` and `APP_TRUSTED_PROXY_IPS` is empty.

#### Scenario: Trusted proxy header is honored

- **GIVEN** `APP_TRUSTED_PROXY_IPS=10.0.0.0/8`
- **AND** the proxy-headers middleware is installed
- **WHEN** a request arrives from socket peer `10.1.2.3` with header `X-Forwarded-For: 1.2.3.4`
- **THEN** the rate-limit key includes `1.2.3.4`, not `10.1.2.3`

#### Scenario: Untrusted proxy header is ignored

- **WHEN** a request arrives from socket peer `203.0.113.10` (not in trusted ranges) with header `X-Forwarded-For: 1.2.3.4`
- **THEN** the rate-limit key includes `203.0.113.10`, not `1.2.3.4`

#### Scenario: Production refuses empty trusted-proxy list

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_TRUSTED_PROXY_IPS` unset
- **WHEN** `AppSettings.validate_production()` runs
- **THEN** the returned error list includes a message naming `APP_TRUSTED_PROXY_IPS`

## ADDED Requirements

### Requirement: Per-account lockout limiter

In addition to the per-(ip, email) burst limiter, every rate-limited authentication route SHALL also check a per-account limiter keyed on the email (or `user_id` if resolved). Both checks MUST pass for the request to proceed. The per-account window and cap are configured independently via `APP_AUTH_PER_ACCOUNT_<ACTION>_WINDOW_SECONDS` and `APP_AUTH_PER_ACCOUNT_<ACTION>_MAX_ATTEMPTS`.

#### Scenario: Per-account lockout fires regardless of IP diversity

- **GIVEN** `APP_AUTH_PER_ACCOUNT_LOGIN_MAX_ATTEMPTS=5`
- **WHEN** 5 failed login attempts arrive for `victim@example.com` from 5 distinct client IPs within the per-account window
- **THEN** the 6th attempt — from a 6th distinct IP — is rejected with the rate-limit error
- **AND** the log entry distinguishes the trip as `per_account` (not `per_ip`)

#### Scenario: Per-account limiter independence from per-(ip, email)

- **GIVEN** `APP_AUTH_PER_ACCOUNT_LOGIN_MAX_ATTEMPTS=5` and a per-(ip, email) cap of 3 within a shorter window
- **WHEN** the per-(ip, email) limiter trips first on the 4th attempt from a single IP
- **THEN** the response is the rate-limit error
- **AND** the log entry tags the trip as `per_ip` (not `per_account`)
- **AND** the per-account counter has not yet reached its cap

### Requirement: In-process limiter is bounded

`FixedWindowRateLimiter` SHALL use a bounded data structure (e.g. `cachetools.TTLCache`) for its in-memory counter, with a `ttl` greater than the longest configured window so no key is evicted while still inside its rate-limit window. Memory usage MUST NOT grow unboundedly with the number of distinct (IP, email) pairs.

#### Scenario: Cache size stays bounded under key explosion

- **GIVEN** a `FixedWindowRateLimiter` with `maxsize=10` and `ttl=300`
- **WHEN** the limiter is exercised with 100 distinct keys in succession
- **THEN** the internal cache size never exceeds 10

#### Scenario: TTL exceeds the longest configured window

- **GIVEN** a `FixedWindowRateLimiter` constructed with the longest configured window of 60 seconds
- **WHEN** the limiter records an attempt under key `K` at time T0
- **AND** time advances to T0 + 60 seconds
- **THEN** key `K` is still present in the internal cache (`ttl > longest_window` guarantees it has not been evicted while still inside its rate-limit window)

### Requirement: Distributed rate limiter and principal cache are required in multi-worker production

When `APP_ENVIRONMENT=production`, the production validator SHALL refuse to start unless `APP_AUTH_REDIS_URL` is set. This applies to both the rate-limit backend and the principal-cache backend; the default for `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT` MUST be `true`.

#### Scenario: Missing Redis URL in production fails validation

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_AUTH_REDIS_URL` unset
- **WHEN** `AppSettings.validate_production()` runs
- **THEN** the returned error list includes a message naming `APP_AUTH_REDIS_URL`
- **AND** the message mentions both the rate limiter and the principal cache
