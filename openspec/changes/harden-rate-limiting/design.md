## Depends on

- `strengthen-test-contracts` (recommended) — ships the `RateLimiterContract` + `PrincipalCacheContract` that protect the flipped defaults against silent regression. Not a hard build dep; this change can land first if necessary.

## Conflicts with

- `harden-auth-defense-in-depth`, `strengthen-production-validators`: all three append entries to `AuthenticationSettings.validate_production` / `AppSettings.validate_production` / `ApiSettings.validate_production`. No logical conflict — merge friction only.
- `add-error-reporting-seam`, `harden-http-middleware-stack`, `expose-domain-metrics`: also edit `src/app_platform/api/app_factory.py`. Order: install `ProxyHeadersMiddleware` first (before any middleware that reads `request.client`); other middleware changes layer on top.
- `preserve-error-response-headers`: defines the `Retry-After` header path triggered by the limiter — coordinate so the `RateLimitExceededError` shape matches.
- `improve-db-performance`: shares `src/app_platform/config/sub_settings.py`. Merge-friction only.

## Context

The auth rate limiter is the only thing standing between the public internet and `/auth/login`. Its current implementation works on a developer laptop and fails silently in every realistic production topology. The four gaps are independent — each fix is small in isolation — but they need to land together because partial fixes still leave the system trivially bypassable (e.g. fixing the proxy-headers issue without per-account lockout still lets a botnet credential-stuff one account).

The codebase already exposes the right seams: rate-limit settings live in `AuthenticationSettings`, the limiter is selected by composition based on `APP_AUTH_REDIS_URL`, and `validate_production` already refuses other unsafe defaults. This proposal extends those existing patterns; it does not introduce a new mechanism.

## Goals / Non-Goals

**Goals**
- Real client IPs reach the limiter even behind a proxy.
- Per-account brute-force protection regardless of attacker IP diversity.
- In-process limiter is bounded; cannot be used as a DOS vector.
- Multi-worker production deploys cannot boot in the silently-broken configuration.

**Non-Goals**
- A full WAF / bot-detection layer. Out of scope.
- Cross-region distributed coordination.
- Changing the rate-limit algorithm (still fixed-window for in-process, sliding-window for Redis).

## Decisions

### Decision 1: Use the ProxyHeaders middleware, not parse headers ourselves

- **Chosen**: install Starlette's `ProxyHeadersMiddleware` (or the Uvicorn equivalent) configured via `APP_TRUSTED_PROXY_IPS`.
- **Rationale**: well-tested, RFC 7239 compliant, less surface area than a custom parser.
- **Rejected**: roll our own `X-Forwarded-For` parser.
- **Rejected**: trust `X-Forwarded-For` unconditionally — spoofable.

### Decision 2: Two independent limiters per action, AND-composed

- **Chosen**: a per-(ip, email) burst limiter AND a per-account absolute limiter. Both must pass.
- **Rationale**: lets the two windows be tuned independently; supports distinct logging for IP-vs-account-targeted attacks.
- **Rejected**: a single limiter with multiple keys.

### Decision 3: TTLCache for the in-process limiter

- **Chosen**: `cachetools.TTLCache(maxsize=10_000, ttl=longest_window + 60)`.
- **Rationale**: bounds memory, evicts oldest entries, `ttl > longest_window` prevents evicting a key that's still inside its rate-limit window.
- **Rejected**: switching the in-process limiter to a sliding window. Precision wins live in the Redis variant.

### Decision 4: Flip `auth_require_distributed_rate_limit` to `True` by default

- **Chosen**: distributed-state is the default for production. Dev unaffected because `validate_production` only runs when `APP_ENVIRONMENT=production`.
- **Rationale**: the current default's silent-failure mode is exactly how the gap survived.
- **Rejected**: keep the default `false` and rely on docs.

## Risks / Trade-offs

- **Risk**: misconfigured `APP_TRUSTED_PROXY_IPS` (too permissive) is worse than the current state — attacker can spoof `X-Forwarded-For`. Mitigation: validator requires a non-empty list; docs explicitly warn against `0.0.0.0/0`; tests cover both correct and incorrect configurations.
- **Risk**: per-account lockout enables a DoS-by-lockout attack. Mitigation: lockout is a per-window rate limit (not an all-time suspension); distinct logging lets ops detect sustained patterns.
- **Trade-off**: the per-account limiter adds one Redis round trip per login (~1 ms; negligible vs Argon2's ~150 ms).

## Migration Plan

Single PR; no schema changes.

1. Add `trusted_proxy_ips` setting; install middleware; gate `validate_production`.
2. Add per-account knobs + AND-composition in route handlers.
3. Swap `_attempts: dict` for `TTLCache`.
4. Flip default + extend validator for distributed principal cache.
5. Tests (5 unit + 1 integration).

Rollback: revert; no persistence.
