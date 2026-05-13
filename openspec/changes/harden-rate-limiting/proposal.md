## Why

The auth rate-limit story has four independent gaps that compound into "the rate limit isn't really protecting anything":

1. **IP source is the direct socket peer.** `src/features/authentication/adapters/inbound/http/auth.py:51-53` reads `request.client.host`. Behind any production load balancer that's the proxy's IP, identical for every real client → one attacker exhausts the bucket for the entire user base.
2. **No per-account lockout.** The limiter key is `path:ip:email`. An attacker with a botnet of N IPs (each under the limit) can credential-stuff any single account indefinitely.
3. **In-process counter leaks memory.** `FixedWindowRateLimiter._attempts` is a plain dict keyed on `path:ip:email`; nothing ever evicts.
4. **Multi-worker silently weakens limits.** Default in-process limiter + in-process principal cache mean every limit is multiplied by worker count and revoked admins keep acting on workers that didn't see the invalidation. The production validator already refuses `auth_require_distributed_rate_limit=true` without Redis, but the flag itself defaults to `false`.

## What Changes

- Install Starlette's `ProxyHeadersMiddleware` gated on a new `APP_TRUSTED_PROXY_IPS` setting; production validator refuses an empty value.
- Add a second limiter keyed on the account itself (`per-account-login`, `per-account-reset`, `per-account-verify`) AND-composed with the existing per-(ip, email) limiter.
- Replace `FixedWindowRateLimiter._attempts` with `cachetools.TTLCache(maxsize=10_000, ttl=longest_window + 60)`.
- Flip the default for `auth_require_distributed_rate_limit` to `True`. Extend the production validator to refuse the in-process principal cache when `APP_AUTH_REDIS_URL` is unset.

**Capabilities — Modified**
- `authentication`: tightens the rate-limit requirement and the multi-worker/distributed-state requirement.

## Impact

- **Code**:
  - `src/app_platform/api/app_factory.py` — install `ProxyHeadersMiddleware` ahead of any middleware that reads `request.client`.
  - `src/app_platform/config/sub_settings.py` — add `trusted_proxy_ips: list[str]` on `ApiSettings`; `ApiSettings.validate_production` appends an error when empty.
  - `src/app_platform/config/settings.py` — surface `APP_TRUSTED_PROXY_IPS`; flip `auth_require_distributed_rate_limit` default to `True`.
  - `src/features/authentication/composition/settings.py` — `per_account_login_max_attempts`, `per_account_login_window_seconds`, `per_account_reset_*`, `per_account_verify_*`. Extend `validate_production` to refuse the in-process principal cache when `APP_AUTH_REDIS_URL` is unset.
  - `src/features/authentication/adapters/inbound/http/auth.py` — `_client_ip(request)` helper; per-account `_account_key`; AND-compose both limiters in `login`, `register`, `request_password_reset`, `request_email_verification`.
  - `src/features/authentication/application/rate_limit.py` — swap `_attempts: dict` for `cachetools.TTLCache(maxsize=10_000, ttl=longest_window + 60)`.
- **Migrations**: none.
- **Production**: deploys missing `APP_TRUSTED_PROXY_IPS` or `APP_AUTH_REDIS_URL` (with multi-worker) refuse to start. Intentional — these were already silently broken.
- **Tests**:
  - `src/app_platform/tests/test_settings.py` — production validator refuses empty `APP_TRUSTED_PROXY_IPS` and in-process principal cache without Redis.
  - `src/features/authentication/tests/unit/` — proxy-header trust tests; per-account lockout across distinct IPs; `TTLCache` eviction.
  - `src/features/authentication/tests/integration/` — Redis-backed per-account lockout end-to-end.
- **Docs**: `docs/operations.md`, `CLAUDE.md` Key env vars, `.env.example` commented examples.
- **Backwards compatibility**: dev (single worker, no proxy) unaffected — new validator entries gated on `APP_ENVIRONMENT=production`.
