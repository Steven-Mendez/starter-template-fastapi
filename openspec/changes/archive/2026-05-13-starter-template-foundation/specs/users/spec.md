## ADDED Requirements

### Requirement: Users is a self-contained feature slice

The system SHALL host user-identity concerns in a dedicated feature slice at `src/features/users/`. The slice SHALL contain the `User` SQLModel table, the `UserPort` inbound port, the use cases for register, get-by-id, get-by-email, update-profile, deactivate, and list-users (admin), the adapters that implement the authorization feature's `UserRegistrarPort` and `UserAuthzVersionPort`, and the HTTP routes for user profile and admin user listing. The slice SHALL NOT contain credentials, password hashes, JWT issuance, sessions, refresh tokens, or any authentication-flow logic.

#### Scenario: Users owns the User entity and its lifecycle

- **WHEN** the codebase is loaded
- **THEN** `src/features/users/adapters/outbound/persistence/sqlmodel/models.py` defines `UserTable`
- **AND** `src/features/users/application/use_cases/` contains modules for register, get_by_id, get_by_email, update_profile, deactivate, list_users
- **AND** no module under `src/features/users/` references `password_hash`, JWT, refresh tokens, or password reset

#### Scenario: Users does not import from authentication

- **WHEN** the codebase is loaded
- **THEN** no module under `src/features/users/` imports from `src/features/authentication/`
- **AND** the import-linter contract "Users does not import from authentication" passes

### Requirement: UserPort is the only contract authentication uses to reach users

The users feature SHALL expose a single inbound port `UserPort` with the methods `get_by_id`, `get_by_email`, `create`, `update_profile`, and `deactivate`. The authentication feature SHALL depend on this port and SHALL NOT import the `UserTable` SQLModel class or any users-feature use case directly.

#### Scenario: Authentication takes UserPort as a dependency

- **WHEN** any use case under `src/features/authentication/application/` reads or writes a user record
- **THEN** the use case takes `UserPort` as a constructor dependency
- **AND** no module under `src/features/authentication/` imports `UserTable` or any module under `src/features/users/adapters/`

#### Scenario: UserPort.get_by_email returns None for unknown emails

- **WHEN** `UserPort.get_by_email("does-not-exist@example.com")` is called
- **THEN** the result is `None`
- **AND** the call SHALL NOT raise

#### Scenario: UserPort.create rejects a duplicate email

- **GIVEN** a user with email `"x@example.com"` already exists
- **WHEN** `UserPort.create(email="x@example.com", display_name="...")` is called
- **THEN** the call returns `Err(DuplicateEmailError)`
- **AND** no second row is inserted

### Requirement: Users implements UserRegistrarPort and UserAuthzVersionPort

The users feature SHALL provide two adapters that implement the authorization feature's outbound ports: a `UserRegistrarPort` adapter (used by `BootstrapSystemAdmin`) that is idempotent on email, and a `UserAuthzVersionPort` adapter that increments `users.authz_version`. These adapters SHALL be the only mechanism by which authorization affects user-shaped state.

#### Scenario: UserRegistrarAdapter is idempotent on email

- **GIVEN** a user with email `"x@example.com"` already exists
- **WHEN** `register_or_lookup(email="x@example.com", password="...")` is called
- **THEN** the call returns the existing user's id
- **AND** the call SHALL NOT create a duplicate user
- **AND** the call SHALL NOT raise `DuplicateEmailError`

#### Scenario: UserAuthzVersionAdapter bumps the user's authz_version

- **GIVEN** a user with `authz_version = N`
- **WHEN** the users-feature `SQLModelUserAuthzVersionAdapter.bump(user_id)` is called
- **THEN** the row's `authz_version` becomes `N + 1`
- **AND** the row's `updated_at` is set to the current UTC time

### Requirement: User profile endpoints live in users

The HTTP routes `GET /me`, `PATCH /me`, and `DELETE /me` (deactivate self) SHALL be served by the users feature. The route `GET /admin/users` SHALL also be served by the users feature (moved from authentication), gated by `require_authorization("manage_users", "system", None)`.

#### Scenario: GET /me returns the calling user's profile

- **GIVEN** an authenticated user `u1`
- **WHEN** `u1` calls `GET /me`
- **THEN** the response status is 200
- **AND** the response body contains `u1`'s id, email, display_name, is_active, and created_at

#### Scenario: GET /admin/users requires system:main#admin

- **GIVEN** user `u1` has no relationship tuple on `system:main`
- **WHEN** `u1` calls `GET /admin/users`
- **THEN** the response status is 403
- **AND** when `u1` is granted `system:main#admin`, the next call returns 200

### Requirement: The users table loses the password_hash column

The `users` table owned by this feature SHALL contain `id`, `email`, `display_name`, `is_active`, `authz_version`, `created_at`, `updated_at`. The column `password_hash` SHALL NOT exist on this table; it is owned by the authentication feature's `credentials` table.

#### Scenario: Schema does not include password_hash

- **WHEN** the database schema is inspected after `alembic upgrade head`
- **THEN** the `users` table has no column named `password_hash`
- **AND** the column has been moved to a separate `credentials` table owned by authentication
