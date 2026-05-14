# authentication Specification

## Purpose
TBD - created by archiving change split-authentication-and-authorization. Update Purpose after archive.
## Requirements
### Requirement: Authentication is a self-contained feature slice

The system SHALL host authentication concerns in a dedicated feature slice at ``src/features/auth/``. The slice SHALL contain user registration, password hashing, login, JWT issuance and decoding, refresh-token rotation, logout, password reset, and email verification. The slice SHALL NOT contain authorization concerns (relationship tuples, ReBAC engine, action registry, parent walks).

#### Scenario: Auth owns the user-shaped state

- **WHEN** the codebase is loaded
- **THEN** ``src/features/auth/`` contains the ``UserTable``, ``RefreshTokenTable``, ``AuthInternalTokenTable``, and ``AuthAuditEventTable`` SQLModel definitions
- **AND** ``src/features/auth/application/`` contains the use cases for register, login, refresh, logout, password reset, email verify, and resolve-principal
- **AND** ``src/features/auth/`` contains no module under ``application/authorization/`` or ``adapters/outbound/authorization/``

#### Scenario: Auth does not import from authorization

- **WHEN** the codebase is loaded
- **THEN** no module under ``src/features/auth/`` imports from ``src/features/authorization/``
- **AND** the import-linter contract "Auth and authorization are independent features" passes

### Requirement: Auth implements UserAuthzVersionPort and UserRegistrarPort

The auth feature SHALL expose two adapter classes that satisfy ports defined by the authorization feature: a ``UserAuthzVersionPort`` adapter that increments ``users.authz_version``, and a ``UserRegistrarPort`` adapter that registers a new user (or returns an existing one) by email. These adapters SHALL be the only mechanism by which authorization can affect user-shaped state.

#### Scenario: UserAuthzVersionAdapter bumps the user's authz_version

- **GIVEN** a user with ``authz_version = N``
- **WHEN** the auth-feature ``SQLModelUserAuthzVersionAdapter.bump(user_id)`` is called
- **THEN** the row's ``authz_version`` becomes ``N + 1``
- **AND** the ``updated_at`` is set to the current UTC time

#### Scenario: UserRegistrarAdapter is idempotent on email

- **WHEN** ``register_or_lookup(email="x", password="...")`` is called and a user with email ``x`` already exists
- **THEN** the call returns the existing user's id
- **AND** the call SHALL NOT create a duplicate user
- **AND** the call SHALL NOT raise ``DuplicateEmailError`` (the contract is idempotent on email)

### Requirement: Auth audit events accept writes from the authorization feature

The auth feature SHALL expose an ``AuditPort`` adapter that the authorization feature uses to record events of type ``authz.*`` (e.g., ``authz.bootstrap_admin_assigned``). Audit events SHALL continue to live in the ``auth_audit_events`` table; the schema is unchanged.

#### Scenario: Authorization records a bootstrap event via AuditPort

- **WHEN** authorization's ``BootstrapSystemAdmin`` use case writes the system-admin tuple
- **THEN** an audit event of type ``authz.bootstrap_admin_assigned`` appears in ``auth_audit_events`` with ``user_id`` set to the bootstrapped user

### Requirement: Auth admin endpoints stay in auth

The HTTP routes ``GET /admin/users`` and ``GET /admin/audit-log`` SHALL continue to be served by the auth feature. They SHALL be gated by the platform-level ``require_authorization`` dependency on ``system:main`` (``manage_users`` and ``read_audit`` actions respectively), exactly as today.

#### Scenario: Admin routes resolve through the platform dependency

- **WHEN** a request hits ``GET /admin/users``
- **THEN** the route's dependency is ``require_authorization("manage_users", "system", None)``
- **AND** the dependency reads ``app.state.authorization`` (which holds the authorization feature's port instance)
- **AND** the use case ``ListUsers`` is the auth feature's existing implementation

### Requirement: Token re-issuance invalidates prior unused tokens

`RequestPasswordReset` and `RequestEmailVerification` SHALL, inside the same transaction that inserts the new token, stamp `used_at = now()` on every prior unused token row for the same `(user_id, purpose)`. Only the most-recently-issued token MUST remain live.

#### Scenario: Re-issued reset invalidates the prior one

- **GIVEN** a user with one unused password-reset token issued at time T0
- **WHEN** the user requests another password reset at time T1
- **THEN** the T0 token's `used_at` is set
- **AND** the T1 token's `used_at` is NULL
- **AND** a confirm attempt with the T0 token returns `Err(TokenAlreadyUsed)`

#### Scenario: Re-issued verification invalidates the prior one

- **GIVEN** a user with one unused email-verification token issued at time T0
- **WHEN** the user requests another verification email at time T1
- **THEN** the T0 token's `used_at` is set
- **AND** the T1 token's `used_at` is NULL
- **AND** a confirm attempt with the T0 token returns `Err(TokenAlreadyUsed)`

#### Scenario: Invalidation runs in the same transaction as the insert

- **GIVEN** a `RequestPasswordReset` invocation wired to a transaction that will fail to commit
- **WHEN** the use case runs to the point of insert and the transaction rolls back
- **THEN** prior tokens for `(user_id, "password_reset")` are still unstamped (`used_at IS NULL`)
- **AND** no new token row is present

### Requirement: Self-deactivation invalidates all session artifacts

`DELETE /me` SHALL, in a single response cycle, (1) clear the browser-side refresh cookie via `Set-Cookie` with empty value + `Max-Age=0` + `Path=/auth` and (2) revoke every server-side refresh-token family for the deactivated user inside the same Unit of Work that flips `is_active=False`. The server-side revocation MUST run inline (not via the outbox) so the response reflects revoked state.

(Note: this change does NOT introduce a deactivation audit event. `DeactivateUser` currently records none; if one is needed, it is the responsibility of a separate change.)

#### Scenario: Self-deactivate clears the cookie

- **GIVEN** an authenticated session whose refresh cookie is set
- **WHEN** the client sends `DELETE /me`
- **THEN** the response status is 204 (or the project's existing self-deactivate status)
- **AND** the response includes `Set-Cookie: refresh_token=; Max-Age=0; Path=/auth`

#### Scenario: Refresh after self-deactivate is rejected

- **GIVEN** a client that captured its refresh cookie before sending `DELETE /me`
- **WHEN** the client replays the captured cookie against `POST /auth/refresh`
- **THEN** the response status is 401
- **AND** no new access token is issued

#### Scenario: Server-side revocation runs inline

- **GIVEN** a `DeactivateUser` use case wired with a recording `RevokeAllRefreshTokens` collaborator
- **WHEN** `DELETE /me` is invoked and the use case returns `Ok`
- **THEN** the collaborator records exactly one invocation with the deactivated `user_id`
- **AND** the invocation occurred before the HTTP response was returned (no outbox round trip)

### Requirement: User registration is atomic

The `RegisterUser` use case SHALL commit the new `User` row, the matching `Credential` row, and the `auth.user_registered` audit event in a single database transaction. A failure in any one of these writes MUST roll back the other two, leaving the database in the pre-registration state.

#### Scenario: Credential write failure rolls back the user row

- **GIVEN** a `RegisterUser` call with email `new@example.com` and a valid password
- **AND** the credential adapter is configured to raise on `upsert_credential` after the user row has been written
- **WHEN** the use case executes
- **THEN** the result is `Err(...)`
- **AND** a subsequent `UserPort.get_by_email("new@example.com")` returns `None`
- **AND** no audit event is recorded for that email

#### Scenario: Happy path commits once

- **GIVEN** a fresh database
- **WHEN** `RegisterUser` succeeds for email `ok@example.com`
- **THEN** exactly one transaction is committed (observable in DB logs or via a test fixture that counts commits)
- **AND** all three rows (user, credential, audit event) are present

### Requirement: Password-reset confirmation is atomic

The `ConfirmPasswordReset` use case SHALL commit the credential upsert, the reset-token consumption (`used_at`), the refresh-token revocation, and the audit event in a single database transaction. A failure in any write MUST roll back the credential update, leaving the user's password unchanged.

#### Scenario: Token-consumption failure preserves the old password

- **GIVEN** a valid unconsumed password-reset token for user `u`
- **AND** the internal-token writer is configured to raise on `mark_internal_token_used`
- **WHEN** `ConfirmPasswordReset` executes
- **THEN** `u`'s credential still matches the original password
- **AND** the reset token is still marked unconsumed
- **AND** existing refresh tokens for `u` are still valid

### Requirement: Email-verification confirmation is atomic and lock-protected

The `ConfirmEmailVerification` use case SHALL read the verification token with a row lock (`FOR UPDATE`) inside a transaction that also performs `mark_user_verified`, `mark_internal_token_used`, and the audit event. Two concurrent submissions of the same token MUST result in exactly one success and exactly one audit event.

#### Scenario: Concurrent submissions are serialized

- **GIVEN** a valid unconsumed email-verification token for user `u`
- **WHEN** two threads submit the same token concurrently against a real Postgres database
- **THEN** exactly one thread receives `Ok(...)`; the other receives an `Err` indicating the token was already used
- **AND** exactly one `auth.email_verified` audit event is recorded
- **AND** `u.is_verified` is `true`

### Requirement: AuthRepositoryPort exposes a registration transaction

The `AuthRepositoryPort` SHALL expose a `register_user_transaction()` context manager. Inside the context, callers receive a writer with `create_user(...)`, `upsert_credential(...)`, and `record_audit_event(...)` methods. The writer MUST NOT auto-commit per call. On normal exit the surrounding session commits; on exception it rolls back.

#### Scenario: Writer methods do not auto-commit

- **GIVEN** an open `register_user_transaction()` context
- **WHEN** the caller invokes `create_user(...)` and then exits the context via exception
- **THEN** the user row is not visible from a separate connection
- **AND** no `UserTable` row exists for that email

### Requirement: AuthInternalTokenTransactionPort covers credential upsert and user verification

The internal-token transaction writer SHALL expose `upsert_credential(...)` and `mark_user_verified(...)` alongside the existing token-consumption methods, so that `ConfirmPasswordReset` and `ConfirmEmailVerification` can run their complete state changes inside one transaction.

#### Scenario: Password-reset confirmation is atomic across token consumption and credential upsert

- **GIVEN** an open internal-token transaction for a password-reset confirmation
- **WHEN** `upsert_credential(...)` raises after the token row has been marked consumed
- **THEN** the surrounding session rolls back
- **AND** the reset token row is still in its pre-consumption state when read from a separate connection
- **AND** the credential row is unchanged

#### Scenario: Email-verification confirmation is atomic across token consumption and user-verified flag

- **GIVEN** an open internal-token transaction for an email-verification confirmation
- **WHEN** `mark_user_verified(...)` and the token-consumption update both succeed and the context exits normally
- **THEN** a separate connection observes `is_verified = true` AND the token marked consumed in the same snapshot
- **AND** neither change is observable from a separate connection before the context exits

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

### Requirement: Expired and revoked tokens are periodically purged

The authentication feature SHALL provide a `PurgeExpiredTokens` use case that deletes rows from `refresh_tokens` (where `expires_at` or `revoked_at` is older than the retention cutoff) and from `auth_internal_tokens` (where `used_at` or `expires_at` is older than the retention cutoff). The retention cutoff is `now() - APP_AUTH_TOKEN_RETENTION_DAYS` (default 7 days). The worker SHALL run the use case on a cron at the interval configured by `APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES` (default 60). Deletions MUST be batched (10000 rows per statement, looped until empty) to avoid long-running locks.

#### Scenario: Expired refresh-token rows are deleted

- **GIVEN** 100 refresh-token rows with `expires_at = now() - 30 days`
- **WHEN** `PurgeExpiredTokens.execute(retention_days=7)` runs
- **THEN** all 100 rows are deleted
- **AND** rows with `expires_at` within the last 7 days are preserved

#### Scenario: Expired internal-token rows are deleted

- **GIVEN** 500 internal-token rows with `used_at = now() - 30 days`
- **WHEN** `PurgeExpiredTokens.execute(retention_days=7)` runs
- **THEN** all 500 rows are deleted
- **AND** unused rows with `expires_at` in the future are preserved

#### Scenario: Large purges are batched

- **GIVEN** 30000 expired refresh-token rows
- **WHEN** the use case runs
- **THEN** all 30000 rows are deleted
- **AND** the implementation executed at least three batched `DELETE ... LIMIT 10000` statements

#### Scenario: Rows inside the retention window are preserved

- **GIVEN** a refresh-token row with `revoked_at = now() - 1 day` and `expires_at = now() + 7 days`
- **AND** an internal-token row with `used_at = now() - 1 day` and `expires_at = now() + 1 day`
- **WHEN** `PurgeExpiredTokens.execute(retention_days=7)` runs
- **THEN** both rows are still present
- **AND** the returned `PurgeReport` records zero deletions for each table

### Requirement: Per-account lockout limiter

In addition to the per-(ip, email) burst limiter, every rate-limited authentication route SHALL also check a per-account limiter keyed on the email (or `user_id` if resolved). Both checks MUST pass for the request to proceed. The per-account window and cap are configured independently via `APP_AUTH_PER_ACCOUNT_<ACTION>_WINDOW_SECONDS` and `APP_AUTH_PER_ACCOUNT_<ACTION>_MAX_ATTEMPTS`.

#### Scenario: Per-account lockout fires regardless of IP diversity

- **GIVEN** `APP_AUTH_PER_ACCOUNT_LOGIN_MAX_ATTEMPTS=5`
- **WHEN** 5 failed login attempts arrive for `victim@example.com` from 5 distinct client IPs within the per-account window
- **THEN** the 6th attempt — from a 6th distinct IP — is rejected with the rate-limit error
- **AND** the log entry distinguishes the trip as `per_account` (not `per_ip`)

#### Scenario: Per-account limiter independence from per-(ip, email)

- **GIVEN** `APP_AUTH_PER_ACCOUNT_LOGIN_MAX_ATTEMPTS=5` and a per-(ip, email) cap of 3 within a shorter window
- **WHEN** the per-(ip, email) limiter trips first on the 4th attempt from a single IP
- **THEN** the response is the rate-limit error
- **AND** the log entry tags the trip as `per_ip` (not `per_account`)
- **AND** the per-account counter has not yet reached its cap

### Requirement: In-process limiter is bounded

`FixedWindowRateLimiter` SHALL use a bounded data structure (e.g. `cachetools.TTLCache`) for its in-memory counter, with a `ttl` greater than the longest configured window so no key is evicted while still inside its rate-limit window. Memory usage MUST NOT grow unboundedly with the number of distinct (IP, email) pairs.

#### Scenario: Cache size stays bounded under key explosion

- **GIVEN** a `FixedWindowRateLimiter` with `maxsize=10` and `ttl=300`
- **WHEN** the limiter is exercised with 100 distinct keys in succession
- **THEN** the internal cache size never exceeds 10

#### Scenario: TTL exceeds the longest configured window

- **GIVEN** a `FixedWindowRateLimiter` constructed with the longest configured window of 60 seconds
- **WHEN** the limiter records an attempt under key `K` at time T0
- **AND** time advances to T0 + 60 seconds
- **THEN** key `K` is still present in the internal cache (`ttl > longest_window` guarantees it has not been evicted while still inside its rate-limit window)

### Requirement: Distributed rate limiter and principal cache are required in multi-worker production

When `APP_ENVIRONMENT=production`, the production validator SHALL refuse to start unless `APP_AUTH_REDIS_URL` is set. This applies to both the rate-limit backend and the principal-cache backend; the default for `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT` MUST be `true`.

#### Scenario: Missing Redis URL in production fails validation

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_AUTH_REDIS_URL` unset
- **WHEN** `AppSettings.validate_production()` runs
- **THEN** the returned error list includes a message naming `APP_AUTH_REDIS_URL`
- **AND** the message mentions both the rate limiter and the principal cache
