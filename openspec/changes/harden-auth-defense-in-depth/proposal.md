## Why

Three smaller hardening gaps in the auth surface, each defensible but together meaningful:

1. **Login timing reveals user existence.** `LoginUser.execute` (`src/features/authentication/application/use_cases/auth/login_user.py:62-71`) verifies a dummy hash on the no-user branch (good), but only the hit-branch runs `get_credential_for_user` — one extra DB roundtrip. The timing skew between hit and miss (~5–20 ms in a healthy connection pool) is enough for a determined attacker to enumerate registered emails.
2. **`_enforce_cookie_origin` is bypassable when `Origin` is absent.** `adapters/inbound/http/auth.py:121-123` returns OK whenever the `Origin` header is missing. SameSite=strict (the default for the refresh cookie) protects against this in real browsers, but `auth_cookie_samesite` is configurable to `none`, and the validator does not refuse it in production. With `samesite=none`, a top-level form POST omitting `Origin` carries the cookie and passes the check.
3. **`request_password_reset` enumeration via timing.** The use case returns immediately on unknown email and opens a transaction + writes three rows on known email (`request_password_reset.py:47-55`). Latency delta (~10–100 ms) is measurable. Same applies to `request_email_verification`.

None of these are catastrophic on their own. Each is the kind of thing a determined attacker chains with the others (and with the rate-limit gaps in `harden-rate-limiting`) into a working enumeration → credential-stuffing pipeline.

## What Changes

- **Login**: equalize DB roundtrips between hit and miss. Always run a `get_credential_for_user(user.id if user else SENTINEL)` and always perform exactly one `verify_password` call against the stored hash or a fixed-cost dummy Argon2 hash. Compare the boolean verification result using a constant-time equality primitive so branch selection is not observable.
- **`_enforce_cookie_origin`**: when the `Origin` header is absent, require `Referer` to match the trusted-origin set instead. If both are absent on a request that carries the refresh cookie, refuse with 403. Additionally, extend `AuthenticationSettings.validate_production` to refuse `auth_cookie_samesite="none"`.
- **`request_password_reset` and `request_email_verification`**: on unknown-email branches, run `verify_password(FIXED_DUMMY_ARGON2_HASH, request.email)` exactly once so the wall-clock of the unknown-email branch matches the dominant Argon2-class cost of the known-email branch. No DB writes on the unknown branch, no `time.sleep`, no shadow transactions.

**Capabilities — Modified**
- `authentication`: tightens the login + cookie-origin + reset/verify-issuance requirements.

**Capabilities — New**
- None.

## Impact

- **Code**:
  - `src/features/authentication/application/use_cases/auth/login_user.py` — `_NoCredentialUserId` sentinel; always-one-DB-roundtrip + always-one-verify; constant-time comparison of the verify result.
  - `src/features/authentication/adapters/inbound/http/auth.py` — `_enforce_cookie_origin` rewrites the missing-Origin branch to require Referer; rejects with 403 when both absent and refresh cookie present.
  - `src/features/authentication/application/use_cases/auth/request_password_reset.py` — unknown-email branch calls `verify_password(FIXED_DUMMY_ARGON2_HASH, request.email)`.
  - `src/features/authentication/application/use_cases/auth/request_email_verification.py` — same.
  - `src/features/authentication/composition/settings.py` — `AuthenticationSettings.validate_production` refuses `auth_cookie_samesite="none"`.
- **Migrations**: none.
- **Production**: legitimate clients are unaffected. Enumeration latency-skew attacks become noticeably harder.
- **Tests**:
  - `src/features/authentication/tests/unit/` — `LoginUser` roundtrip-count parity; reset/verify roundtrip-count parity (assert exactly one verify call in both branches); cookie-origin tests across four header combinations × cookie-present-or-absent; validator test for `samesite=none` refusal.
  - `src/features/authentication/tests/integration/` — Postgres-backed wall-clock parity for login (50 hits vs 50 misses); same for reset/verify.
- **Backwards compatibility**: existing browsers send `Origin` on POSTs; the new "require Origin OR Referer" rule does not break them. The `samesite=none` refusal only fires in production.
