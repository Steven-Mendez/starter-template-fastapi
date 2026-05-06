## Why

The current `FixedWindowRateLimiter` stores attempt counts in process memory, which means each server instance enforces limits independently. Running multiple replicas behind a load balancer divides the effective limit proportionally, allowing an attacker to make N × max_attempts login attempts before being blocked. Adding Redis as a shared counter store makes the limit apply globally across all instances.

## What Changes

- Add a Redis service to the Docker Compose setup alongside the existing PostgreSQL service.
- Implement a `RedisRateLimiter` that satisfies the same `check(key)` interface as `FixedWindowRateLimiter`.
- Wire the new limiter into `AuthContainer` when a Redis URL is configured, falling back to the in-memory limiter when it is not.
- Add `AUTH_REDIS_URL` to `AppSettings` and `.env.example`.

## Capabilities

### New Capabilities

- `distributed-rate-limiting`: A Redis-backed rate limiter that enforces login/auth attempt limits globally across all server replicas using atomic INCR + EXPIRE.

### Modified Capabilities

_(none — the existing auth endpoints do not change behavior from the client's perspective)_

## Impact

- `docker-compose.yml`: new Redis service.
- `src/features/auth/application/rate_limit.py`: new `RedisRateLimiter` class.
- `src/features/auth/composition/container.py`: conditional limiter selection based on settings.
- `src/platform/config/settings.py`: new `auth_redis_url` optional field.
- `.env.example`: new `APP_AUTH_REDIS_URL` variable.
- New dependency: `redis` (Python client).
