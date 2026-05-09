## ADDED Requirements

### Requirement: Auth feature provides per-port test fakes
The auth feature SHALL provide test fakes implementing the existing outbound port protocols (defined in `src/features/auth/application/ports/outbound/auth_repository.py`). The fakes SHALL live in `src/features/auth/tests/fakes/` and SHALL be deterministic, resettable, and usable across multiple unit tests without shared state.

Required fakes (using the existing port names — not introducing new port classes):

- `FakeAuthRepository` implementing `AuthRepositoryPort` (or its narrower sub-protocols `UserRepositoryPort`, `TokenRepositoryPort`, `RBACRepositoryPort`, `AuditRepositoryPort`) with in-memory dict-backed storage. SHALL include `reset()` and SHALL correctly implement `revoke_refresh_family(family_id)` and `revoke_user_refresh_tokens(user_id)`.
- `FakeClock` (controllable time source) and `FakeIdGenerator` (deterministic IDs).

#### Scenario: FakeAuthRepository stores and retrieves users
- **WHEN** `FakeAuthRepository.create_user(email=..., password_hash=...)` is called followed by `FakeAuthRepository.get_user_by_email(email)`
- **THEN** the same user record is returned

#### Scenario: FakeAuthRepository revokes by family
- **WHEN** three refresh tokens sharing `family_id="abc"` are saved and `revoke_refresh_family("abc")` is called inside the transaction context
- **THEN** all three tokens are marked revoked when retrieved by hash

### Requirement: Registration use case has unit test coverage
Unit tests for user registration SHALL cover: successful registration, duplicate email rejection, and password hash storage. Tests SHALL use `FakeAuthRepository` and `FakeClock`. The use case under test is the `RegisterUser` per-use-case class introduced by the `hexagonal-architecture-refactor` change.

#### Scenario: Successful registration returns Ok with tokens
- **WHEN** `RegisterUser.execute(RegisterCommand(email="new@example.com", password="..."))` is called against a fresh fake repository
- **THEN** the result is `Ok(IssuedTokens(...))` with a non-empty access token

#### Scenario: Duplicate email returns Err
- **WHEN** a user with `email="existing@example.com"` already exists in the fake repository and `RegisterUser.execute(...)` is called with the same email
- **THEN** the result is `Err(DuplicateEmailError(...))` and no exception is raised

#### Scenario: Password is hashed before storage
- **WHEN** `RegisterUser.execute(...)` succeeds
- **THEN** the user stored in the fake repository has `password_hash` set and it is not equal to the raw password

### Requirement: Login use case has unit test coverage
Unit tests for login SHALL cover: successful login, wrong password, unknown email (constant-time path), and inactive user rejection.

#### Scenario: Valid credentials return Ok with tokens
- **WHEN** `LoginUser.execute(LoginCommand(email=..., password=...))` matches a stored user
- **THEN** the result is `Ok(IssuedTokens(...))`

#### Scenario: Wrong password returns Err
- **WHEN** `LoginUser.execute(LoginCommand(email=..., password="wrong"))` is called
- **THEN** the result is `Err(InvalidCredentialsError(...))` with no exception

#### Scenario: Unknown email returns Err and runs constant-time path
- **WHEN** `LoginUser.execute(LoginCommand(email="ghost@example.com", password=...))` is called against an empty fake repository
- **THEN** the result is `Err(InvalidCredentialsError(...))` (not a distinct user-not-found error) AND the `PasswordService.verify` path was invoked against a dummy hash (timing parity with the wrong-password case)

#### Scenario: Inactive user is rejected
- **WHEN** `LoginUser.execute(...)` is called with credentials matching a user whose `is_active=False`
- **THEN** the result is `Err(InvalidCredentialsError(...))` (preserving the no-enumeration policy)

### Requirement: Refresh token use case has unit test coverage
Unit tests for token refresh SHALL cover: successful rotation, reuse of an already-rotated token (family revocation), and expired token rejection.

#### Scenario: Valid refresh token produces new token pair
- **WHEN** `RefreshToken.execute(RefreshCommand(token=valid_token))` is called
- **THEN** the result is `Ok(IssuedTokens(...))` with a new access token and the previous refresh token marked rotated in the fake store

#### Scenario: Reused refresh token revokes the entire family
- **WHEN** a previously rotated token is submitted to `RefreshToken.execute(...)`
- **THEN** the result is `Err(InvalidTokenError(...))` (or a subclass) AND all tokens in the family are revoked in the fake store

#### Scenario: Expired refresh token is rejected
- **WHEN** `RefreshToken.execute(...)` is called with a token whose `expires_at` is in the past per `FakeClock`
- **THEN** the result is `Err(InvalidTokenError(...))`

### Requirement: RBAC assignment use cases have unit test coverage
Unit tests for RBAC SHALL cover: role assignment, permission grant, and that a role grant bumps `authz_version` for affected users (so the principal cache is invalidated).

#### Scenario: Assigning a role increments authz_version for the user
- **WHEN** `AssignRole.execute(AssignRoleCommand(user_id=..., role_id=...))` is called
- **THEN** the stored user has `authz_version` incremented by at least 1

#### Scenario: Granting a permission to a role bumps authz_version for all users in that role
- **WHEN** `GrantPermission.execute(GrantPermissionCommand(role_id=..., permission_id=...))` is called and two users hold that role
- **THEN** both users' `authz_version` is incremented in the fake repository

#### Scenario: Granting a permission to a role is persisted
- **WHEN** `GrantPermission.execute(...)` is called
- **THEN** the role in the fake repository includes the permission in its permission set

### Requirement: Auth unit tests run via existing test target
The new tests SHALL live under `src/features/auth/tests/unit/` and run as part of `make test-feature FEATURE=auth` and `make test`. Their existence SHALL NOT require any new test runner configuration.

#### Scenario: Tests are discoverable by the standard test target
- **WHEN** `make test-feature FEATURE=auth` is run
- **THEN** all new application-layer use case tests are collected and executed
