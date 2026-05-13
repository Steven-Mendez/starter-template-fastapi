## MODIFIED Requirements

### Requirement: Login DB roundtrip count is identical for hit and miss

`LoginUser.execute` SHALL make the same number of database queries regardless of whether the supplied email matches an existing user. `get_credential_for_user` MUST be called exactly once in both branches (using a sentinel user-id that returns `None` on the miss branch). Exactly one `verify_password` call MUST happen in both branches, against the stored credential's hash on the hit branch and against a fixed-cost dummy Argon2 hash on the miss branch. The boolean verification result MUST be compared using a constant-time equality primitive before any branch decision.

#### Scenario: Hit and miss issue the same query count

- **GIVEN** a `LoginUser` instance wired to repos that record their `get_credential_for_user` and `verify_password` calls
- **WHEN** the use case is invoked once with a known email and once with an unknown email
- **THEN** `get_credential_for_user` was called exactly once in each invocation
- **AND** `verify_password` was called exactly once in each invocation

#### Scenario: Wall-clock parity over a sample (Postgres-backed)

- **GIVEN** 100 login attempts for a registered email and 100 for an unregistered email, executed against a real Postgres instance
- **WHEN** the **medians** of the two latency distributions are compared (median is robust to CI scheduler noise; means are not)
- **THEN** the absolute difference is less than 20 ms (loose enough to survive containerized CI; the proof of equalization is the call-count assertion in the unit test, not a tight wall-clock bound)

### Requirement: Cookie-bearing state changes require an explicit origin signal

The `_enforce_cookie_origin` check on routes that read the refresh cookie SHALL refuse with HTTP 403 when both `Origin` and `Referer` headers are missing AND the refresh cookie is present on the request. When either header is present, its origin MUST match the trusted-origin set. When the refresh cookie is absent on the request, the check is a no-op.

The production validator MUST refuse `APP_AUTH_COOKIE_SAMESITE=none`.

#### Scenario: Missing both Origin and Referer with cookie present is refused

- **GIVEN** a request to `/auth/refresh` carrying the refresh cookie and no `Origin` or `Referer` headers
- **WHEN** the route handler runs
- **THEN** the response status is 403
- **AND** no refresh-token mutation occurred

#### Scenario: Referer fallback when Origin is absent

- **GIVEN** a request to `/auth/refresh` carrying the refresh cookie, no `Origin` header, and `Referer: https://app.example.com/dashboard`
- **AND** `https://app.example.com` is in the trusted-origin set
- **WHEN** the route handler runs
- **THEN** the request proceeds normally

#### Scenario: Missing both headers but no cookie is a no-op

- **GIVEN** a request with no `Origin`, no `Referer`, and no refresh cookie
- **WHEN** `_enforce_cookie_origin` runs
- **THEN** it returns without raising; the route proceeds normally

#### Scenario: `samesite=none` refused in production

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_AUTH_COOKIE_SAMESITE=none`
- **WHEN** `AppSettings.validate_production()` runs
- **THEN** the returned error list names `APP_AUTH_COOKIE_SAMESITE`

### Requirement: Password-reset and email-verification issuance hides user existence via fixed-cost dummy hash

The `RequestPasswordReset` and `RequestEmailVerification` use cases SHALL, on the unknown-email branch, invoke `verify_password(FIXED_DUMMY_ARGON2_HASH, request.email)` exactly once before returning `Ok`. The dominant Argon2 cost of this call MUST match the dominant Argon2-class cost of the known-email branch within a small wall-clock bound (target: mean delta < 10 ms over a sample of 50 calls each). The unknown-email branch MUST NOT call `time.sleep` and MUST NOT perform DB writes.

#### Scenario: Verify is called exactly once in both branches

- **GIVEN** a `RequestPasswordReset` instance wired to a recording credential-verifier
- **WHEN** the use case is invoked once with a known email and once with an unknown email
- **THEN** `verify_password` was called exactly once in each invocation

#### Scenario: Known and unknown emails produce comparable latency

- **GIVEN** 50 password-reset requests for a registered email and 50 for an unregistered email, executed against a real Postgres instance
- **WHEN** the **medians** of the two latency distributions are compared (robust to CI scheduler noise)
- **THEN** the absolute difference is less than 30 ms (the call-count parity test in `harden-auth-defense-in-depth/tasks 4.3` is the load-bearing assertion; this scenario is a smoke check)
