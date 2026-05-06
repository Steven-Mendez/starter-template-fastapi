## 1. Dependencies And Configuration

- [x] 1.1 Add `redis` Python package to `pyproject.toml` dependencies
- [x] 1.2 Add `auth_redis_url: str | None = None` field to `AppSettings`
- [x] 1.3 Add `APP_AUTH_REDIS_URL` entry to `.env.example` with a commented-out example value

## 2. Redis Rate Limiter Implementation

- [x] 2.1 Add `RedisRateLimiter` class to `rate_limit.py` with `check(key)` and `reset()` matching `FixedWindowRateLimiter`'s interface
- [x] 2.2 Implement atomic INCR + conditional EXPIRE logic in `check()` using `redis-py` sync client
- [x] 2.3 Add `close()` method to `RedisRateLimiter` that disposes the Redis connection

## 3. Container Wiring

- [x] 3.1 Update `build_auth_container` in `container.py` to instantiate `RedisRateLimiter` when `settings.auth_redis_url` is set, `FixedWindowRateLimiter` otherwise
- [x] 3.2 Extend the `shutdown` callback in `AuthContainer` to call `close()` on the limiter if the limiter exposes it

## 4. Docker Compose

- [x] 4.1 Add a `redis` service to `docker-compose.yml` using the official `redis:7-alpine` image
- [x] 4.2 Set `APP_AUTH_REDIS_URL=redis://redis:6379/0` on the API service in `docker-compose.yml`

## 5. Tests And Validation

- [x] 5.1 Add a unit test for `RedisRateLimiter` using `fakeredis` or a mock to verify INCR logic, window expiry, and the limit error
- [x] 5.2 Verify existing auth e2e tests still pass (rate limiting is disabled in tests via `auth_rate_limit_enabled=False`)
- [x] 5.3 Confirm `build_auth_container` selects the correct limiter based on `auth_redis_url` presence
