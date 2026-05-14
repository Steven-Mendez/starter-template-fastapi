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
