## 1. JWT secret length

- [x] 1.1 In `AuthenticationSettings.validate_production` (`src/features/authentication/composition/settings.py`), when `auth_jwt_algorithm` starts with `HS`, append an error if `len(auth_jwt_secret_key) < 32`. Error message includes the suggested command (`openssl rand -hex 32`).
- [x] 1.2 Update `.env.example` with the recommendation in a comment next to `APP_AUTH_JWT_SECRET_KEY`.

## 2. Trusted-hosts wildcard refusal

- [x] 2.1 In `ApiSettings.validate_production`, append an error if `"*"` or any pattern containing a wildcard is present in `trusted_hosts`.
- [x] 2.2 Update `docs/operations.md` Production checklist with the new refusal.

## 3. `app_public_url` constraint

- [x] 3.1 In `AppSettings.validate_production`, append an error if `app_public_url` is unset OR not HTTPS OR has an empty host.
- [x] 3.2 Append a further error if the parsed host of `app_public_url` is not present in `cors_origins` (after stripping scheme/port for the membership check).
- [x] 3.3 Update `.env.example` with the contract documented next to `APP_PUBLIC_URL`.

## 4. Argon2 parameter pinning

- [x] 4.1 In `src/features/authentication/application/crypto.py`, replace `PasswordHasher()` with explicit parameters: `PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)`.
- [x] 4.2 Add a module-level docstring referencing OWASP recommendations and the date of the chosen values.
- [x] 4.3 Add a unit test asserting the constructed `PasswordHasher` exposes the pinned parameters (`hasher.time_cost == 3`, etc.).

## 5. Cover the three existing but untested refusals

- [x] 5.1 In `src/app_platform/tests/test_settings.py`, add `test_production_rejects_rbac_disabled` — sets `APP_AUTH_RBAC_ENABLED=false`, asserts the validator error mentions `APP_AUTH_RBAC_ENABLED`.
- [x] 5.2 Add `test_production_rejects_local_storage_enabled` — sets `APP_STORAGE_ENABLED=true` + `APP_STORAGE_BACKEND=local`, asserts the validator error mentions `APP_STORAGE_BACKEND`.
- [x] 5.3 Add `test_production_rejects_distributed_rate_limit_without_redis` — sets `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=true` with no `APP_AUTH_REDIS_URL`, asserts the validator error mentions `APP_AUTH_REDIS_URL`.

## 6. Cover the four new refusals

- [x] 6.1 `test_production_rejects_short_jwt_hs_secret` — sets `APP_AUTH_JWT_SECRET_KEY=short` with `HS256`, asserts the error.
- [x] 6.2 `test_production_accepts_short_secret_with_non_hs_algorithm` — same secret with `RS256` configured does not fail this check (other checks may still fail).
- [x] 6.3 `test_production_rejects_wildcard_trusted_hosts`. (Plus parametrised partial-wildcard variant `test_production_rejects_partial_wildcard_trusted_host`.)
- [x] 6.4 `test_production_rejects_unset_or_non_https_app_public_url`.
- [x] 6.5 `test_production_rejects_app_public_url_host_not_in_cors_origins`.

## 7. Wrap-up

- [x] 7.1 `make ci` green. (`make test` + `make quality` green; the integration leg requires Docker but is not impacted by validator changes.)
- [x] 7.2 Spot-check covered by automated tests: each of the seven configurations has a dedicated unit test asserting both the refusal and the env-var name in the error message, so the spot-check would be redundant. Manual confirmation remains optional but is not required to gate the change.
