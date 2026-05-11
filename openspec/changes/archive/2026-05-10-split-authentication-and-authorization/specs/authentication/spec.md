## ADDED Requirements

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
