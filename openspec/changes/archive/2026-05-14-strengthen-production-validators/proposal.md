## Why

The production validator in `AppSettings.validate_production` (and the per-feature `validate_production` methods it composes) is the project's defense-in-depth against shipping with an unsafe configuration. It already covers many cases (CORS wildcards, console email backend, in-process job backend, etc.). Four entries are missing, and they correspond to real ways the system can ship broken:

1. **JWT secret length is not enforced.** Validator only checks `auth_jwt_secret_key` is truthy. A deploy with `APP_AUTH_JWT_SECRET_KEY=hunter2` boots fine; with HS256 (the default), short or low-entropy secrets are brute-forceable from a single captured token.
2. **`trusted_hosts=["*"]` is permitted in production.** Default is `["*"]`, validator never refuses it, `TrustedHostMiddleware` is then effectively a no-op for Host-header spoofing protection.
3. **`app_public_url` is unvalidated.** It's interpolated verbatim into password-reset and email-verification links. A misconfigured (or attacker-influenced) value silently directs reset tokens off-platform.
4. **Argon2 parameters are unpinned.** `PasswordHasher()` relies on library defaults; those happen to meet OWASP 2024 today, but silently change across `argon2-cffi` upgrades. Two production deploys with different lib versions can rehash at materially different cost.

Also: the validator already has good test coverage for the cases it does check, but three documented refusals have no test (`APP_AUTH_RBAC_ENABLED=false`, `APP_STORAGE_BACKEND=local` with `APP_STORAGE_ENABLED=true`, `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=true` without `APP_AUTH_REDIS_URL`). Silent regression of any of those would not be caught by CI.

## What Changes

- Extend `AuthenticationSettings.validate_production` to enforce `len(auth_jwt_secret_key) >= 32` when `auth_jwt_algorithm` starts with `HS`. Provide a clear error message naming `openssl rand -hex 32`.
- Extend `ApiSettings.validate_production` to refuse `"*"` (or any wildcard host) in `trusted_hosts`.
- Add a new validation entry for `app_public_url`: MUST be set, MUST be HTTPS, MUST have a non-empty host, AND its host MUST match one of the entries in `cors_origins` (after canonicalization). Refuse otherwise.
- Pin Argon2 parameters explicitly in `application/crypto.py`: `PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)`. Document them in `docs/operations.md`.
- Add unit tests for the three existing-but-untested refusals plus the four new ones.

**Capabilities — Modified**
- `authentication`: tightens production-validator requirements.

**Capabilities — New**
- None.

## Impact

- **Code**: `authentication/composition/settings.py` (new validator entries + Argon2 pin), `app_platform/config/settings.py` (`app_public_url` validation), `app_platform/config/sub_settings.py` (`trusted_hosts` refusal), `application/crypto.py` (pinned `PasswordHasher`).
- **Migrations**: none.
- **Production**: deploys with any of the four unsafe configurations now fail loudly at startup. None of these should be present in a healthy production deploy.
- **Tests**: seven new unit tests in `app_platform/tests/test_settings.py`.
- **Backwards compatibility**: development is unaffected — all new checks are gated on `APP_ENVIRONMENT=production`.
