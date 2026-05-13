## MODIFIED Requirements

### Requirement: Authentication is a self-contained feature slice

The system SHALL host authentication concerns in a dedicated feature slice at `src/features/authentication/` (renamed from `src/features/auth/`). The slice SHALL contain login, JWT issuance and decoding, refresh-token rotation, logout, password reset, email verification, principal resolution, and the `credentials` table that stores password hashes. The slice SHALL NOT contain the `User` entity or its table (owned by the users feature), authorization engine code (owned by the authorization feature), or any feature-specific authorization vocabulary.

#### Scenario: Authentication owns credentials and session state

- **WHEN** the codebase is loaded
- **THEN** `src/features/authentication/` contains `CredentialsTable`, `RefreshTokenTable`, `AuthInternalTokenTable`, and `AuthAuditEventTable` SQLModel definitions
- **AND** `src/features/authentication/application/` contains the use cases for login, refresh, logout, password reset, email verify, and resolve-principal
- **AND** `src/features/authentication/` contains no SQLModel definition of `UserTable`

#### Scenario: Authentication does not import from authorization or users adapters

- **WHEN** the codebase is loaded
- **THEN** no module under `src/features/authentication/` imports from `src/features/authorization/`
- **AND** no module under `src/features/authentication/` imports from `src/features/users/adapters/`
- **AND** the import-linter contract "Authentication and authorization are independent features" passes
- **AND** the import-linter contract "Authentication uses users only via UserPort" passes

### Requirement: Authentication audit events accept writes from the authorization feature

The authentication feature SHALL expose an `AuditPort` adapter that the authorization feature uses to record events of type `authz.*` (e.g., `authz.bootstrap_admin_assigned`). Audit events SHALL continue to live in the `auth_audit_events` table; the schema is unchanged.

#### Scenario: Authorization records a bootstrap event via AuditPort

- **WHEN** authorization's `BootstrapSystemAdmin` use case writes the system-admin tuple
- **THEN** an audit event of type `authz.bootstrap_admin_assigned` appears in `auth_audit_events` with `user_id` set to the bootstrapped user

### Requirement: Authentication admin endpoints are limited to the audit log

The HTTP route `GET /admin/audit-log` SHALL continue to be served by the authentication feature, gated by the platform-level `require_authorization` dependency on `system:main#read_audit`. The endpoint `GET /admin/users` SHALL be served by the users feature instead.

#### Scenario: Audit-log route resolves through the platform dependency

- **WHEN** a request hits `GET /admin/audit-log`
- **THEN** the route's dependency is `require_authorization("read_audit", "system", None)`
- **AND** the dependency reads `app.state.authorization` (which holds the authorization feature's port instance)
- **AND** the use case `ListAuditEvents` is the authentication feature's existing implementation

#### Scenario: Admin users route is no longer served by authentication

- **WHEN** the route table of the application is inspected
- **THEN** `GET /admin/users` is registered by the users feature
- **AND** the authentication feature's router does not declare any route at `/admin/users`

## ADDED Requirements

### Requirement: Credentials are stored in a separate table owned by authentication

The system SHALL persist password credentials in a `credentials` table owned by the authentication feature. Each row SHALL contain `user_id`, `algorithm`, `hash`, `last_changed_at`, `created_at`. The table SHALL enforce uniqueness on `(user_id, algorithm)` so a user can hold at most one credential of a given algorithm. The previous `users.password_hash` column SHALL be dropped after a two-phase migration completes.

#### Scenario: Password is stored in credentials, not in users

- **WHEN** a user registers with a password
- **THEN** a row appears in `credentials` with `user_id = <new_user.id>`, `algorithm = "argon2"`, and a non-empty `hash`
- **AND** the `users` row contains no `password_hash` column

#### Scenario: Two-phase migration preserves login during rollout

- **GIVEN** the deployment is at phase 1 (`credentials` exists, `users.password_hash` still present and populated)
- **WHEN** a login attempt arrives for a user whose hash has not yet been copied into `credentials`
- **THEN** the login falls back to reading `users.password_hash`
- **AND** the login succeeds when the hash matches the input password
- **AND** the read path logs a structured event `auth.credentials.fallback_used` so the operator can monitor the rollout

#### Scenario: Phase 2 drops the legacy column

- **WHEN** the phase-2 migration runs
- **THEN** the `users` table no longer has a `password_hash` column
- **AND** the fallback path is removed from the codebase

### Requirement: Authentication uses UserPort for all user lookups

The authentication feature SHALL depend on the users feature's `UserPort` for every read or write that touches the `User` entity. The authentication feature SHALL NOT import `UserTable` or any module under `src/features/users/adapters/`.

#### Scenario: Login resolves the user through UserPort

- **WHEN** `LoginUser.execute(email, password)` runs
- **THEN** the use case calls `UserPort.get_by_email(email)` to resolve the user
- **AND** the use case reads the credential from its own `credentials` table by `user_id`
- **AND** no module under `src/features/authentication/` imports `UserTable`

#### Scenario: Registration creates the user via UserPort and then writes credentials

- **WHEN** `RegisterUser.execute(email, password, display_name)` runs
- **THEN** the use case calls `UserPort.create(email=..., display_name=...)`
- **AND** the use case writes a row to its own `credentials` table for the returned user id
- **AND** both writes participate in the same unit of work

### Requirement: Password-reset and email-verify flows deliver via EmailPort

The `RequestPasswordReset` and `RequestEmailVerification` use cases SHALL deliver their tokens to the user by rendering a template registered with the email feature and enqueueing a `send_email` background job (via `JobQueuePort`). The response body of `POST /auth/password-reset` and `POST /auth/email-verify` SHALL NOT contain the token unless `APP_AUTH_RETURN_INTERNAL_TOKENS=true`.

#### Scenario: Reset response contains no token in production-shaped config

- **GIVEN** `APP_AUTH_RETURN_INTERNAL_TOKENS=false`
- **WHEN** a client calls `POST /auth/password-reset` with a valid email
- **THEN** the response status is 202
- **AND** the response body contains no `token` field
- **AND** the `send_email` queue has one new job whose payload contains the rendered email body

#### Scenario: Production refuses APP_AUTH_RETURN_INTERNAL_TOKENS=true

- **GIVEN** `APP_AUTH_RETURN_INTERNAL_TOKENS=true` and `APP_ENVIRONMENT=production`
- **WHEN** the application starts
- **THEN** startup fails with a settings validation error naming the flag

## REMOVED Requirements

### Requirement: Auth implements UserAuthzVersionPort and UserRegistrarPort

**Reason**: These adapters move to the users feature. Authentication no longer owns the `User` entity, so it cannot implement ports that mutate user-shaped state. The contracts themselves (defined in `src/features/authorization/application/ports/outbound/`) are unchanged.

**Migration**: The new `users` feature exposes `SQLModelUserAuthzVersionAdapter` and `SQLModelUserRegistrarAdapter`. `main.py` wires the users-feature implementations into the authorization container instead of the auth-feature ones. See `specs/users/spec.md` for the corresponding scenarios.

### Requirement: Auth admin endpoints stay in auth

**Reason**: `GET /admin/users` moves to the users feature. The remaining admin endpoint owned by authentication (`GET /admin/audit-log`) is covered by the new "Authentication admin endpoints are limited to the audit log" requirement above.

**Migration**: Clients of `GET /admin/users` see no change at the URL level — the route still exists and behaves identically; only the implementing feature changed. The `require_authorization("manage_users", "system", None)` gate is unchanged.
