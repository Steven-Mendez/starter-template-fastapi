## MODIFIED Requirements

### Requirement: Bootstrap depends on UserRegistrarPort

The ``BootstrapSystemAdmin`` use case SHALL live in ``src/features/authorization/application/use_cases/`` and SHALL depend on ``UserRegistrarPort`` (defined in authorization's outbound ports). It SHALL NOT import ``RegisterUser`` or any other auth-feature symbol.

`BootstrapSystemAdmin` SHALL only promote a user to `system:main#admin` under one of three conditions:

1. **Create-and-grant** — no user exists with the configured email; the use case creates the user and grants the relationship.
2. **Idempotent no-op** — a user exists with the configured email AND already holds `system:main#admin`; the use case returns success without writing.
3. **Explicit opt-in promotion** — a user exists with the configured email, does NOT yet hold `system:main#admin`, AND `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`, AND the supplied bootstrap password verifies successfully against the user's stored credential.

In any other case (an existing non-admin user without the opt-in, or with the opt-in but a wrong password) the use case MUST return an `Err` and MUST NOT write a relationship row or any other state.

Every successful grant (paths 1 and 3) MUST emit an `authz.system_admin_bootstrapped` audit event whose payload distinguishes the `subevent="created"` and `subevent="promoted_existing"` cases.

#### Scenario: No existing user — create-and-grant

- **GIVEN** no user exists with email `admin@example.com`
- **AND** `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL=admin@example.com`, `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_PASSWORD=Sufficient!Pa55word`
- **WHEN** the application starts and `BootstrapSystemAdmin` runs
- **THEN** a user is created with email `admin@example.com`
- **AND** the relationship `system:main#admin@user:<new-id>` is written
- **AND** an `authz.system_admin_bootstrapped` audit event with `subevent="created"` is recorded

#### Scenario: Existing non-admin user without opt-in — refuse

- **GIVEN** a user already exists with email `admin@example.com` and does NOT hold `system:main#admin`
- **AND** `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING` is unset or `false`
- **WHEN** `BootstrapSystemAdmin` runs
- **THEN** the use case returns `Err(BootstrapRefusedExistingUserError)`
- **AND** no relationship row is written
- **AND** no audit event is recorded
- **AND** the bootstrap caller (in `src/main.py` / the CLI) logs an ERROR line including the user id and the remediation hint pointing at `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING`
- **AND** the bootstrap caller exits non-zero (`SystemExit(2)`), failing the deploy fast rather than starting without an admin

#### Scenario: Existing non-admin user with opt-in and correct password — promote

- **GIVEN** a user exists with email `admin@example.com` whose credential is `argon2($…)` for password `Operator!Pa55word`
- **AND** `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`
- **AND** `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_PASSWORD=Operator!Pa55word`
- **WHEN** `BootstrapSystemAdmin` runs
- **THEN** the relationship `system:main#admin@user:<id>` is written
- **AND** an `authz.system_admin_bootstrapped` audit event with `subevent="promoted_existing"` is recorded

#### Scenario: Existing non-admin user with opt-in and wrong password — refuse

- **GIVEN** a user exists with email `admin@example.com` whose credential matches password `Operator!Pa55word`
- **AND** `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`
- **AND** `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_PASSWORD=Wrong!Pa55word`
- **WHEN** `BootstrapSystemAdmin` runs
- **THEN** the use case returns `Err(BootstrapPasswordMismatchError)`
- **AND** no relationship row is written
- **AND** no audit event is recorded

#### Scenario: Existing user already holds system-admin — idempotent no-op

- **GIVEN** a user exists with email `admin@example.com` and already holds `system:main#admin`
- **WHEN** `BootstrapSystemAdmin` runs
- **THEN** the use case returns `Ok(...)` with no side effects
- **AND** no new audit event is recorded

#### Scenario: Bootstrap composes user registration through the port

- **WHEN** ``BootstrapSystemAdmin.execute(email, password)`` runs against a fresh database (no user with that email)
- **THEN** the use case calls ``UserRegistrarPort.register_or_lookup(email=..., password=...)``
- **AND** the returned ``user_id`` is used to write the system-admin tuple
- **AND** the use case writes one audit event of type ``authz.system_admin_bootstrapped`` via the ``AuditPort``

## ADDED Requirements

### Requirement: CredentialVerifierPort

The `authorization` capability SHALL declare a `CredentialVerifierPort` outbound port with the single method `verify(user_id: UUID, password: str) -> Result[None, CredentialVerificationError]`. The port is implemented by the `authentication` feature. It MUST NOT have side effects (no audit events, no rate-limit counter increments) — it is a pure check used during system-startup flows like `BootstrapSystemAdmin`.

#### Scenario: Verifier accepts a matching credential

- **GIVEN** a user `u` with credential matching password `correct`
- **WHEN** `CredentialVerifierPort.verify(u.id, "correct")` is called
- **THEN** the result is `Ok(None)`

#### Scenario: Verifier rejects a non-matching credential

- **GIVEN** a user `u` with credential matching password `correct`
- **WHEN** `CredentialVerifierPort.verify(u.id, "wrong")` is called
- **THEN** the result is `Err(CredentialVerificationError)`
- **AND** no audit event is emitted
- **AND** no rate-limit counter is incremented
