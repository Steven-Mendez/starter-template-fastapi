## 1. Trusted-proxy IP resolution

- [ ] 1.1 Add `trusted_proxy_ips: list[str] = []` to `ApiSettings` (`src/app_platform/config/sub_settings.py`); env var `APP_TRUSTED_PROXY_IPS` (comma-separated CIDRs).
- [ ] 1.2 In `src/app_platform/api/app_factory.py`, install `uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware` (the canonical implementation; ships with the `fastapi[standard]`/`uvicorn` stack already in use) configured with `trusted_hosts=trusted_proxy_ips`. Install it BEFORE any middleware or route that reads `request.client`. Note: this middleware accepts CIDR-style entries; document `0.0.0.0/0` as the explicit "trust anything" footgun and warn against it in `.env.example`.
- [ ] 1.3 In `ApiSettings.validate_production`, append an error naming `APP_TRUSTED_PROXY_IPS` when `trusted_proxy_ips` is empty.
- [ ] 1.4 In `src/features/authentication/adapters/inbound/http/auth.py`, modify the existing `_client_ip(request)` helper at lines 51-53 to rely on `request.client.host` after the `ProxyHeadersMiddleware` rewrite. No call-site changes — the helper is already in use.

## 2. Per-account lockout limiter

- [ ] 2.1 Add `per_account_login_max_attempts: int = 20`, `per_account_login_window_seconds: int = 3600` to `AuthenticationSettings` (`src/features/authentication/composition/settings.py`); same pair for `reset` and `verify`.
- [ ] 2.2 Add an `_account_key(action, identifier)` helper in `auth.py`; identifier is the email pre-resolution, or `user_id` once resolved.
- [ ] 2.3 In each rate-limited route handler (`login`, `register`, `request_password_reset`, `request_email_verification`), invoke the per-account limiter AFTER the per-(ip, email) one. Both must pass.
- [ ] 2.4 On a per-account trip, emit a distinct log event tagged `per_account` (vs `per_ip`) so dashboards can separate account-targeted attacks.

## 3. Bounded in-process counter

- [ ] 3.1 In `src/features/authentication/application/rate_limit.py`, replace `_attempts: dict` in `FixedWindowRateLimiter` with `cachetools.TTLCache(maxsize=10_000, ttl=longest_window_seconds + 60)`.
- [ ] 3.2 Unit test in `src/features/authentication/tests/unit/`: allocate >10k distinct keys; assert the cache size never exceeds 10_000.

## 4. Distributed-state production gates

- [ ] 4.1 In `src/app_platform/config/settings.py` (and the `AuthenticationSettings` projection), flip the default of `auth_require_distributed_rate_limit` to `True`.
- [ ] 4.2 In `AuthenticationSettings.validate_production`, append an error naming `APP_AUTH_REDIS_URL` when the principal-cache backend resolves to in-process (or when `APP_AUTH_REDIS_URL` is unset). The message MUST mention both the rate limiter and the principal cache.
- [ ] 4.3 Update `docs/operations.md` Production checklist with both new refusal cases.

## 5. Tests

- [ ] 5.1 Unit: `X-Forwarded-For: 1.2.3.4` from a trusted proxy → `_client_ip` returns `1.2.3.4`; from an untrusted proxy → returns the socket peer.
- [ ] 5.2 Unit: per-account lockout fires after N failures across distinct IPs.
- [ ] 5.3 Unit: `FixedWindowRateLimiter` with `maxsize=10` exercised with 100 distinct keys — cache size stays ≤ 10.
- [ ] 5.4 Unit: production validator refuses empty `APP_TRUSTED_PROXY_IPS`.
- [ ] 5.5 Unit: production validator refuses in-process principal cache without `APP_AUTH_REDIS_URL`.
- [ ] 5.6 Integration: real Redis container; multi-attempt login from two distinct simulated IPs against the same email; per-account limiter trips at the configured threshold.

## 6. Docs

- [ ] 6.1 Update `CLAUDE.md` "Key env vars (auth-related)" with `APP_TRUSTED_PROXY_IPS`, the new per-account knobs, and the now-required `APP_AUTH_REDIS_URL` for multi-worker prod.
- [ ] 6.2 Update `.env.example` with commented examples for `APP_TRUSTED_PROXY_IPS` and the per-account knobs.

## 7. Wrap-up

- [ ] 7.1 `make ci` green.
- [ ] 7.2 Manual: run uvicorn behind a single-IP nginx pointed at multiple replicas; attempt logins from two distinct client IPs; confirm both real IPs appear in rate-limit logs.
