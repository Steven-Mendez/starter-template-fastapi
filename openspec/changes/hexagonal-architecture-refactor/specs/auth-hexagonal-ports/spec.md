## ADDED Requirements

### Requirement: Auth application layer exposes inbound port protocols
The auth feature SHALL expose one `typing.Protocol` per use case in `src/features/auth/application/ports/inbound/`. Each protocol SHALL declare a single `execute(command) -> Result[T, ApplicationError]` method. Auth use-case implementations SHALL be decorated with `@dataclass(slots=True)` and SHALL implement their corresponding inbound port structurally.

Inbound ports cover, at minimum, all current `AuthService` and `RBACService` operations:

- `RegisterUserPort`, `LoginUserPort`, `RefreshTokenPort`, `LogoutUserPort`
- `RequestPasswordResetPort`, `ConfirmPasswordResetPort`
- `RequestEmailVerificationPort`, `ConfirmEmailVerificationPort`
- `ResolvePrincipalFromAccessTokenPort` (used by the FastAPI dependency)
- `AssignRolePort`, `RemoveRolePort`, `GrantPermissionPort`, `RevokePermissionPort` (RBAC)

#### Scenario: RegisterUser use case implements its port protocol
- **WHEN** `RegisterUser` is instantiated and passed to a function typed against `RegisterUserPort`
- **THEN** mypy reports no type error

#### Scenario: LoginUser use case implements its port protocol
- **WHEN** `LoginUser` is instantiated and passed to a function typed against `LoginUserPort`
- **THEN** mypy reports no type error

#### Scenario: RefreshToken use case implements its port protocol
- **WHEN** `RefreshToken` is instantiated and passed to a function typed against `RefreshTokenPort`
- **THEN** mypy reports no type error

#### Scenario: Application layer remains import-clean
- **WHEN** Import Linter checks are run via `make lint-arch`
- **THEN** zero violations are reported for the auth inbound port modules

### Requirement: Auth outbound port protocols are preserved and verified
The auth feature ALREADY exposes `typing.Protocol` interfaces in `src/features/auth/application/ports/outbound/auth_repository.py` (`UserRepositoryPort`, `TokenRepositoryPort`, `RBACRepositoryPort`, `AuditRepositoryPort`, and the composite `AuthRepositoryPort`). The refactor SHALL NOT collapse these ISP slices. Each new per-use-case class SHALL accept the narrowest sub-protocol it actually needs, not the composite `AuthRepositoryPort`.

#### Scenario: SQLModel auth repository continues to satisfy AuthRepositoryPort
- **WHEN** mypy checks `SQLModelAuthRepository` against `AuthRepositoryPort` after the refactor
- **THEN** mypy reports no incompatibility

#### Scenario: RegisterUser depends only on UserRepositoryPort and AuditRepositoryPort
- **WHEN** `RegisterUser` is instantiated in a unit test
- **THEN** only `UserRepositoryPort` and `AuditRepositoryPort` collaborators are required (not `TokenRepositoryPort` or `RBACRepositoryPort`)

#### Scenario: Application layer does not import SQLModel
- **WHEN** Import Linter checks are run via `make lint-arch`
- **THEN** no module under `src/features/auth/application/` imports `sqlmodel`, `sqlalchemy`, or `alembic`

### Requirement: AuthService and RBACService are replaced by per-use-case classes
The monolithic `AuthService` and `RBACService` classes SHALL be decomposed into individual use-case `@dataclass(slots=True)` classes. Each use case SHALL live in `src/features/auth/application/use_cases/<domain>/` (where `<domain>` is `auth/` or `rbac/`). The file `src/features/auth/application/services.py` (re-export shim) SHALL be deleted in this change.

#### Scenario: No import of services.py shim exists after refactor
- **WHEN** `grep -r "from src.features.auth.application.services"` is run against the repository
- **THEN** zero matches are returned

#### Scenario: AuthService class no longer exists
- **WHEN** `grep -rn "class AuthService" src/features/auth/` is run
- **THEN** zero matches are returned

#### Scenario: Each auth use case is independently instantiable
- **WHEN** `RegisterUser(repository=fake_user_repo, audit=fake_audit, password_service=fake_passwords, clock=fake_clock, id_gen=fake_id_gen)` is constructed in a unit test
- **THEN** only the collaborators needed for registration are required; no other use-case dependencies are present

### Requirement: AuthContainer wires per-use-case instances
The `AuthContainer` dataclass in `src/features/auth/composition/container.py` SHALL hold one attribute per use-case instance (replacing the current `auth_service` and `rbac_service` fields). The factory function building the container SHALL inject only the required collaborators into each use case.

#### Scenario: AuthContainer provides register_user use case
- **WHEN** `container.register_user` is accessed
- **THEN** it returns a `RegisterUser` instance implementing `RegisterUserPort`

#### Scenario: AuthContainer provides login_user use case
- **WHEN** `container.login_user` is accessed
- **THEN** it returns a `LoginUser` instance implementing `LoginUserPort`

#### Scenario: AuthContainer no longer exposes the monolithic services
- **WHEN** `container.auth_service` or `container.rbac_service` is accessed after the refactor
- **THEN** an `AttributeError` is raised
