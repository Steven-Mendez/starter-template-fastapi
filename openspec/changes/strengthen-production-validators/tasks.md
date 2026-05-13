## 1. JWT secret length

- [ ] 1.1 In `AuthenticationSettings.validate_production` (`src/features/authentication/composition/settings.py`), when `auth_jwt_algorithm` starts with `HS`, append an error if `len(auth_jwt_secret_key) < 32`. Error message includes the suggested command (`openssl rand -hex 32`).
- [ ] 1.2 Update `.env.example` with the recommendation in a comment next to `APP_AUTH_JWT_SECRET_KEY`.

## 2. Trusted-hosts wildcard refusal

- [ ] 2.1 In `ApiSettings.validate_production`, append an error if `"*"` or any pattern containing a wildcard is present in `trusted_hosts`.
- [ ] 2.2 Update `docs/operations.md` Production checklist with the new refusal.

## 3. `app_public_url` constraint

- [ ] 3.1 In `AppSettings.validate_production`, append an error if `app_public_url` is unset OR not HTTPS OR has an empty host.
- [ ] 3.2 Append a further error if the parsed host of `app_public_url` is not present in `cors_origins` (after stripping scheme/port for the membership check).
- [ ] 3.3 Update `.env.example` with the contract documented next to `APP_PUBLIC_URL`.

## 4. Argon2 parameter pinning

- [ ] 4.1 In `src/features/authentication/application/crypto.py`, replace `PasswordHasher()` with explicit parameters: `PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)`.
- [ ] 4.2 Add a module-level docstring referencing OWASP recommendations and the date of the chosen values.
- [ ] 4.3 Add a unit test asserting the constructed `PasswordHasher` exposes the pinned parameters (`hasher.time_cost == 3`, etc.).

## 5. Cover the three existing but untested refusals

- [ ] 5.1 In `src/app_platform/tests/test_settings.py`, add `test_production_rejects_rbac_disabled` — sets `APP_AUTH_RBAC_ENABLED=false`, asserts the validator error mentions `APP_AUTH_RBAC_ENABLED`.
- [ ] 5.2 Add `test_production_rejects_local_storage_enabled` — sets `APP_STORAGE_ENABLED=true` + `APP_STORAGE_BACKEND=local`, asserts the validator error mentions `APP_STORAGE_BACKEND`.
- [ ] 5.3 Add `test_production_rejects_distributed_rate_limit_without_redis` — sets `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=true` with no `APP_AUTH_REDIS_URL`, asserts the validator error mentions `APP_AUTH_REDIS_URL`.

## 6. Cover the four new refusals

- [ ] 6.1 `test_production_rejects_short_jwt_hs_secret` — sets `APP_AUTH_JWT_SECRET_KEY=short` with `HS256`, asserts the error.
- [ ] 6.2 `test_production_accepts_short_secret_with_non_hs_algorithm` — same secret with `RS256` configured does not fail this check (other checks may still fail).
- [ ] 6.3 `test_production_rejects_wildcard_trusted_hosts`.
- [ ] 6.4 `test_production_rejects_unset_or_non_https_app_public_url`.
- [ ] 6.5 `test_production_rejects_app_public_url_host_not_in_cors_origins`.

## 7. Wrap-up

- [ ] 7.1 `make ci` green.
- [ ] 7.2 Spot-check: boot the app with `APP_ENVIRONMENT=production` (via `make dev` or `fastapi run src/main.py`) under each of the seven configurations and confirm the error message points at the right env var.
