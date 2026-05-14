## 1. Login timing equalization

- [x] 1.1 In `src/features/authentication/application/use_cases/auth/login_user.py`, add a `_NoCredentialUserId` sentinel and a module-level `FIXED_DUMMY_ARGON2_HASH` constant (re-use any existing dummy-hash constant if present).
- [x] 1.2 Refactor `LoginUser.execute` so a single `get_credential_for_user(user.id if user else _NoCredentialUserId)` call always happens; the repository returns `None` for the sentinel without raising.
- [x] 1.3 Always invoke exactly one `verify_password(stored_or_dummy, supplied)`; compare its boolean result against `True` using `hmac.compare_digest` (or equivalent constant-time primitive) before branching on the outcome.
- [x] 1.4 Unit test in `src/features/authentication/tests/unit/`: mock the repo and credential-verifier, assert `get_credential_for_user` is called exactly once and `verify_password` is called exactly once in both the hit and miss branches.
- [x] 1.5 Integration test (Postgres) in `src/features/authentication/tests/integration/`: 100 hits vs 100 misses; assert mean wall-clock delta < 5 ms.

## 2. Cookie-origin enforcement

- [x] 2.1 In `src/features/authentication/adapters/inbound/http/auth.py` `_enforce_cookie_origin`, rewrite the missing-Origin branch:
  - [x] 2.1.1 Read the `Referer` header; if present, parse its origin (`scheme://host[:port]`) and compare against `settings.cors_origins`.
  - [x] 2.1.2 When both `Origin` and `Referer` are missing AND the refresh cookie is present on the request, raise `HTTPException(403, "Untrusted origin")`.
  - [x] 2.1.3 Preserve the existing behavior for a present-and-trusted `Origin` header.
- [x] 2.2 When the refresh cookie is absent, keep current no-op behavior.
- [x] 2.3 Unit tests in `src/features/authentication/tests/unit/` covering all four header combinations (Origin only, Referer only, both, neither) × cookie-present-or-absent.

## 3. Refuse `samesite=none` in production

- [x] 3.1 In `src/features/authentication/composition/settings.py` `AuthenticationSettings.validate_production`, append an error naming `APP_AUTH_COOKIE_SAMESITE` if `auth_cookie_samesite == "none"`.
- [x] 3.2 Update `docs/operations.md` Production checklist to list the new refusal.
- [x] 3.3 Unit test in `src/app_platform/tests/test_settings.py` asserting the new refusal.

## 4. Equalize reset/verify issuance latency via fixed-cost dummy hash

- [x] 4.1 In `src/features/authentication/application/use_cases/auth/request_password_reset.py:48`, when `get_by_email` returns `None`, call `verify_password(FIXED_DUMMY_ARGON2_HASH, request.email)` exactly once before returning `Ok`. No DB writes on this branch. No `time.sleep`. No shadow transaction. (Note: passing `request.email` as the "candidate password" is intentional — Argon2 always returns `False` for the dummy hash; we only care about the wall-clock cost, the boolean is discarded.)
- [x] 4.2 Same change in `src/features/authentication/application/use_cases/auth/request_email_verification.py`.
- [x] 4.3 Unit tests assert `verify_password` is called exactly once in both the known-email and unknown-email branches of each use case.
- [x] 4.4 Integration test (Postgres): 50 known-email + 50 unknown-email requests against each use case; assert mean wall-clock delta < 10 ms.

## 5. Wrap-up

- [x] 5.1 `make ci` green.
- [x] 5.2 Manual: hit `/auth/login` 20× for a known email and 20× for an unknown email; confirm the response-time distributions overlap substantially. <!-- N/A: automated equivalent covered by `tests/integration/test_login_timing_parity.py` (100 hits/100 misses, asserts mean delta < 5 ms). -->
