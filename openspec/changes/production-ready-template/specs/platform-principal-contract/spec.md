## ADDED Requirements

### Requirement: Principal dataclass lives in platform/shared
The system SHALL define a `Principal` frozen dataclass in `src/platform/shared/principal.py`. The dataclass SHALL preserve the exact field set currently defined in `src/features/auth/application/types.py`:

- `user_id: UUID`
- `email: str`
- `is_active: bool`
- `is_verified: bool`
- `authz_version: int`
- `roles: frozenset[str]`
- `permissions: frozenset[str]`

The dataclass SHALL be `@dataclass(frozen=True, slots=True)`. No feature-specific fields SHALL be added. The module SHALL NOT import from any `features` subpackage.

#### Scenario: Principal is importable from platform
- **WHEN** `from src.platform.shared.principal import Principal` is executed
- **THEN** the import succeeds and `Principal` is a frozen, slotted dataclass with the seven fields above

#### Scenario: Platform does not import from features
- **WHEN** `make lint-arch` is run
- **THEN** zero Import Linter violations are reported for `src/platform/shared/principal`

#### Scenario: Auth feature uses platform Principal
- **WHEN** `grep -rn "from src.features.auth.application.types import Principal\|from src.features.auth.application.types import.*Principal" src/` is run
- **THEN** zero matches are returned (all callers use the platform import)

### Requirement: Authorization dependency factory lives in platform/shared
The system SHALL define `build_principal_dependency(resolve_principal: ResolvePrincipalCallable) -> Callable` in `src/platform/shared/authorization.py`. `ResolvePrincipalCallable` is a `Protocol` (or `Callable[[str], Result[Principal, Exception]]`) describing the auth-feature-supplied function that turns a bearer token into a `Principal`. The factory SHALL return a FastAPI-compatible dependency function that:

1. Reads the `Authorization: Bearer <token>` header
2. Calls the supplied resolver
3. Sets `request.state.actor_id` to `principal.user_id`
4. Returns the `Principal`

The `platform/shared/` module MAY import from `fastapi` only if Import Linter allows it; otherwise the FastAPI-aware wrapper SHALL live in `platform/api/` and `platform/shared/` SHALL contain only the framework-agnostic types and the resolver `Protocol`.

#### Scenario: Factory produces a working dependency
- **WHEN** `build_principal_dependency(resolver)` is called with a valid resolver and the returned dependency is invoked on a request carrying a valid JWT
- **THEN** the dependency returns the resolved `Principal` and `request.state.actor_id == principal.user_id`

#### Scenario: Factory-produced dependency rejects missing token
- **WHEN** the dependency is invoked on a request with no Authorization header
- **THEN** the dependency raises HTTP 401

### Requirement: Features depend on platform Principal, not auth internals
Any feature that needs to identify the current user SHALL import `Principal` from `src/platform/shared/principal`. No non-auth feature module (kanban, future features) SHALL import from `src/features/auth/`.

The auth feature itself SHALL re-export `Principal` only as a transitional alias from `src/features/auth/application/types.py` (to keep the diff small while internal call sites migrate); after migration the alias SHALL be removed.

#### Scenario: Kanban imports Principal from platform
- **WHEN** `grep -rn "from src.features.auth" src/features/kanban/` is run
- **THEN** zero matches are returned

#### Scenario: Import Linter confirms no cross-feature imports
- **WHEN** `make lint-arch` is run after the refactor
- **THEN** the cross-feature import contract reports zero violations

#### Scenario: Auth's transitional Principal alias is gone
- **WHEN** the migration completes and `grep -n "^Principal\|^from src.platform.shared.principal import Principal" src/features/auth/application/types.py` is run
- **THEN** `types.py` no longer defines `Principal` locally
