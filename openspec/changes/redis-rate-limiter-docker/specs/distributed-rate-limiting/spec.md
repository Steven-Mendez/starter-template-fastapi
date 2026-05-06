## ADDED Requirements

### Requirement: Redis rate limiter enforces limits globally across replicas
The system SHALL provide a `RedisRateLimiter` that counts attempts in Redis so that the limit applies across all server instances sharing the same Redis instance.

#### Scenario: Attempts counted globally
- **WHEN** two server replicas each receive requests from the same client key
- **THEN** the combined attempt count is enforced against the configured maximum, not each instance's local count

#### Scenario: Limit exceeded returns rate limit error
- **WHEN** a client exceeds `max_attempts` within `window_seconds`
- **THEN** `check(key)` raises `RateLimitExceededError`

#### Scenario: Window resets after expiry
- **WHEN** `window_seconds` have elapsed since the first attempt
- **THEN** the counter resets and the client can make new attempts

### Requirement: Limiter is selected based on configuration
The system SHALL use `RedisRateLimiter` when `AUTH_REDIS_URL` is set, and fall back to `FixedWindowRateLimiter` when it is not.

#### Scenario: Redis URL present activates distributed limiter
- **WHEN** `APP_AUTH_REDIS_URL` is set in the environment
- **THEN** `build_auth_container` connects to Redis and uses `RedisRateLimiter`

#### Scenario: No Redis URL uses in-memory limiter
- **WHEN** `APP_AUTH_REDIS_URL` is not set
- **THEN** `build_auth_container` uses `FixedWindowRateLimiter` as before, with no behavior change

#### Scenario: Invalid Redis URL raises at startup
- **WHEN** `APP_AUTH_REDIS_URL` is set but Redis is unreachable
- **THEN** container construction fails with a clear error rather than silently falling back

### Requirement: Redis service available in Docker Compose
The system SHALL include a Redis service in `docker-compose.yml` so the full stack, including distributed rate limiting, runs with a single `docker compose up`.

#### Scenario: Redis service starts with the stack
- **WHEN** `docker compose up` is run
- **THEN** a Redis instance is available at the default port and the API can connect to it

#### Scenario: Environment variable wires Redis to auth
- **WHEN** `docker-compose.yml` sets `APP_AUTH_REDIS_URL` for the API service
- **THEN** the API uses the distributed limiter without manual configuration
