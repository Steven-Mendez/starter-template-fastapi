## Context

The auth feature ships a `FixedWindowRateLimiter` that counts attempts in process memory. A single `AuthContainer` is created per process, so the limiter works correctly for one server instance. The problem surfaces as soon as more than one replica runs: each has an independent counter, so an attacker can distribute login attempts across replicas and exceed the logical limit undetected.

The fix is to back the counter with Redis, which all replicas share. The rest of the system (endpoints, services, container wiring) must remain unchanged.

Current limiter interface:
```python
class FixedWindowRateLimiter:
    def check(self, key: str) -> None: ...
    def reset(self) -> None: ...
```

## Goals / Non-Goals

**Goals:**
- Add a Redis service to `docker-compose.yml` so the stack is self-contained.
- Add `RedisRateLimiter` implementing the same duck-type interface as `FixedWindowRateLimiter`.
- Select the limiter automatically in `build_auth_container`: Redis when `auth_redis_url` is set, in-memory otherwise.
- Keep backward compatibility: projects that do not set `AUTH_REDIS_URL` continue to use the in-memory limiter unchanged.

**Non-Goals:**
- Replacing Redis with another shared store (Memcached, Postgres).
- Sliding-window or token-bucket algorithms (fixed-window is sufficient for auth throttling).
- Distributed tracing or metrics for rate limit hits.
- TLS or Redis auth for the Docker Compose service (local dev only).

## Decisions

### Redis client library: `redis-py` (sync)

The auth service and repository are fully synchronous (SQLModel sessions). Using `redis-py` in sync mode keeps the stack uniform. The async client (`redis.asyncio`) would require `async def` propagation through `AuthService` and the FastAPI dependencies, which is a larger refactor with no benefit for this use case.

Alternatives considered:
- `aioredis` / `redis.asyncio`: rejected — forces async all the way up, touching endpoints.
- `coredis`: rejected — less standard, smaller ecosystem.

### Atomic INCR + EXPIRE for fixed-window counting

Redis `INCR` is atomic. On the first increment, set `EXPIRE` equal to the window duration. This gives a fixed window anchored at the first attempt rather than a rolling window, matching the current in-memory behavior.

```
INCR  rate:<key>           → count
if count == 1: EXPIRE rate:<key> <window_seconds>
if count > max_attempts: raise RateLimitExceededError
```

Alternatives considered:
- Lua script for atomic INCR+EXPIRE: cleaner but adds complexity; two separate commands are safe because the worst case (race on EXPIRE) only delays expiry by one window, not a security issue.
- Sorted sets for sliding window: more accurate but overkill for auth throttling at this scale.

### Fallback to in-memory when Redis is not configured

`build_auth_container` inspects `settings.auth_redis_url`. If `None`, it builds a `FixedWindowRateLimiter` as today. If set, it connects to Redis and builds a `RedisRateLimiter`. This keeps the feature opt-in and avoids breaking existing single-instance setups.

### Connection is owned by the container, closed on shutdown

`RedisRateLimiter` holds a `redis.Redis` client. The existing `AuthContainer.shutdown` callback pattern is extended to also close the Redis connection when the container shuts down.

## Risks / Trade-offs

- **Redis unavailable at startup** → `build_auth_container` raises at startup rather than silently falling back to in-memory, because silent fallback would defeat the purpose of deploying a distributed limiter. Operators get a clear error on misconfiguration.
- **Redis goes down mid-run** → `check()` raises `ConnectionError`, which is not a subtype of `RateLimitExceededError`. The endpoint will return 500 instead of 429. Acceptable trade-off for a dev/template project; production hardening would wrap connection errors in a try/except and either pass through or fail closed.
- **Fixed-window boundary burst** → An attacker can make 2× max_attempts by hitting the boundary between two windows. This is a known property of fixed-window counters and is acceptable here; the in-memory limiter has the same issue.
- **Docker Compose only** → The Redis service in `docker-compose.yml` is for local development. Production deployments would use a managed Redis (ElastiCache, Upstash, etc.) pointed to by `AUTH_REDIS_URL`.
