## 0. Prerequisite

- [x] 0.1 `hexagonal-architecture-refactor` is merged and `make ci` is green on `main`. This change targets the per-use-case classes (`RegisterUser`, `LoginUser`, ...) and typed `RequestState` introduced by that change.

## 1. Baseline Gate

- [x] 1.1 Run `make ci` and confirm all gates pass; record output as the baseline
- [x] 1.2 Run `grep -rn "from src.features.auth" src/features/kanban/` and document any matches (expected: zero, except for tests fixtures that this change updates)
- [x] 1.3 Run `grep -rn "from src.features.auth.application.types import" src/` and capture the full list of `Principal` import sites to migrate

## 2. Platform Principal Contract

- [x] 2.1 Create `src/platform/shared/principal.py` with `@dataclass(frozen=True, slots=True) Principal`. Field set MUST match the current `auth/application/types.py`: `user_id: UUID, email: str, is_active: bool, is_verified: bool, authz_version: int, roles: frozenset[str], permissions: frozenset[str]`
- [x] 2.2 Decide framework boundary: if Import Linter forbids FastAPI in `platform/shared/`, put framework-agnostic types and a `ResolvePrincipalCallable` `Protocol` in `platform/shared/authorization.py` and the FastAPI-bound `build_principal_dependency`, `require_permissions`, `require_roles`, `require_any_permission` in `platform/api/authorization.py`. Otherwise put everything in `platform/shared/authorization.py`.
- [x] 2.3 Implement `build_principal_dependency(resolver) -> Callable` so the resulting dependency: reads bearer token, calls resolver, calls `set_actor_id(request, principal.user_id)` (typed helper from `hexagonal-architecture-refactor`), returns `Principal`
- [x] 2.4 Implement `require_permissions(*permissions)`, `require_any_permission(*permissions)`, `require_roles(*roles)` — same semantics as the current auth helpers, but consuming the platform `Principal` and respecting `auth_rbac_enabled` via `AuthContainer.settings`
- [x] 2.5 Add transitional `Principal = PlatformPrincipal` re-export in `src/features/auth/application/types.py` so internal callers keep working during the migration
- [x] 2.6 Update `src/features/auth/adapters/inbound/http/dependencies.py`:
  - Import `Principal` from `platform.shared.principal`
  - Replace local `require_permissions`/`require_roles`/`require_any_permission` with thin re-exports from the platform module (or delete and have callers import from platform)
  - Wire `get_current_principal` to delegate to `build_principal_dependency(container.resolve_principal.execute)` — the use-case-based resolver from `hexagonal-architecture-refactor`
- [x] 2.7 Run `grep -rn "from src.features.auth.application.types import Principal" src/` — update each call site to import from `platform.shared.principal`
- [x] 2.8 Remove the local `Principal` definition (and the transitional alias) from `auth/application/types.py`; confirm `grep -rn "^class Principal\b" src/features/auth/` returns zero
- [x] 2.9 Run `make lint-arch` — confirm `platform/shared/principal` and `platform/api/authorization` (or wherever they land) report zero feature imports
- [x] 2.10 Run `make typecheck` — confirm zero new errors

## 3. Kanban RBAC

- [x] 3.1 Update `src/features/auth/application/seed.py`:
  - Add `"kanban:read": "Read kanban boards, columns, and cards"` and `"kanban:write": "Create, update, and delete kanban boards, columns, and cards"` to `ALL_PERMISSIONS`
  - Add both to `ROLE_PERMISSIONS["admin"]`
  - Add `"kanban:read"` to `ROLE_PERMISSIONS["manager"]`
  - Add both to `ROLE_PERMISSIONS["user"]`
  - (`super_admin` inherits all via `set(ALL_PERMISSIONS)`)
- [x] 3.2 Update `src/main.py`:
  - Replace `require_auth = [Depends(get_current_principal)]` with `read_guard = [require_permissions("kanban:read")]` and `write_guard = [require_permissions("kanban:write")]` (sourced from the platform-level helpers)
  - Pass `read_dependencies=read_guard` and `write_dependencies=write_guard` to `mount_kanban_routes`
- [x] 3.3 Update kanban e2e test fixtures (`src/features/kanban/tests/e2e/conftest.py`) so the fake auth dependency injects a `Principal` carrying `kanban:read` + `kanban:write` (and the unauthenticated/no-permission cases test 401 vs 403 distinctly)
- [x] 3.4 Run `grep -rn "from src.features.auth" src/features/kanban/` — confirm zero matches in non-test code; tests update to import the platform `Principal` only
- [x] 3.5 Run `make lint-arch` — confirm zero cross-feature import violations
- [x] 3.6 Run `make test-e2e` — confirm kanban e2e tests pass with RBAC guards

## 4. Delete X-API-Key Infrastructure

- [x] 4.1 Delete `src/platform/api/dependencies/security.py`
- [x] 4.2 Remove `write_api_key: str | None = None` and `write_api_keys: list[str] = []` from `src/platform/config/settings.py`; remove the comment block above them
- [x] 4.3 Remove `APP_WRITE_API_KEY` and `APP_WRITE_API_KEYS` entries from `.env.example`
- [x] 4.4 Delete `src/features/kanban/tests/e2e/test_write_api_key_auth.py`
- [x] 4.5 Remove `secured_settings` and `secured_client` fixtures from `src/features/kanban/tests/e2e/conftest.py`
- [x] 4.6 Run `grep -rn "write_api_key\|require_write_api_key\|X-API-Key" src/ .env.example` — confirm zero matches
- [x] 4.7 Run `make test` — confirm nothing else referenced these

## 5. Lower Principal Cache TTL Default

- [x] 5.1 In `src/platform/config/settings.py`, change `auth_principal_cache_ttl_seconds: int = 30` → `auth_principal_cache_ttl_seconds: int = 5`
- [x] 5.2 In `src/features/auth/application/cache.py:49`, change `InProcessPrincipalCache.create(cls, maxsize: int = 1000, ttl: int = 30)` default → `ttl: int = 5`
- [x] 5.3 Update any settings test that asserts `auth_principal_cache_ttl_seconds == 30` to assert `5`
- [x] 5.4 Update `CLAUDE.md` env-vars table to note the new default and the TTL/revocation-lag tradeoff
- [x] 5.5 Run `make test` — confirm all tests still pass

## 6. Auth Unit Tests

- [x] 6.1 Create `src/features/auth/tests/fakes/__init__.py`
- [x] 6.2 Create `src/features/auth/tests/fakes/fake_auth_repository.py` implementing `AuthRepositoryPort` (or its narrower sub-protocols where the use case under test only needs a slice). Cover at minimum: user CRUD, refresh-token CRUD, refresh-token transaction context (rotation + family revocation), audit recording, RBAC role/permission CRUD, `get_principal`. Include `reset()`.
- [x] 6.3 Create `src/features/auth/tests/fakes/fake_clock.py` (controllable time source) and `fake_id_generator.py` (deterministic UUIDs)
- [x] 6.4 Create `src/features/auth/tests/unit/test_register_user.py` — successful registration, duplicate email returns `Err(DuplicateEmailError)`, password is stored as a hash (not plaintext)
- [x] 6.5 Create `src/features/auth/tests/unit/test_login_user.py` — valid credentials returns `Ok`, wrong password returns `Err(InvalidCredentialsError)`, unknown email returns `Err(InvalidCredentialsError)` AND verify-against-dummy-hash path is invoked, inactive user returns `Err(InvalidCredentialsError)`
- [x] 6.6 Create `src/features/auth/tests/unit/test_refresh_token.py` — valid rotation returns `Ok` and old token marked rotated, reused token returns `Err(InvalidTokenError)` AND family is revoked, expired token returns `Err(InvalidTokenError)`
- [x] 6.7 Create `src/features/auth/tests/unit/test_assign_role.py` — role assignment increments `authz_version` for the user
- [x] 6.8 Create `src/features/auth/tests/unit/test_grant_permission.py` — granting a permission to a role bumps `authz_version` for all users in that role and persists the permission
- [x] 6.9 Run `make test-feature FEATURE=auth` — confirm all new unit tests pass

## 7. Final Gate

- [x] 7.1 Run `make lint` — zero Ruff violations
- [x] 7.2 Run `make lint-arch` — zero Import Linter violations (cross-feature, platform-imports-features)
- [x] 7.3 Run `make typecheck` — zero mypy errors
- [x] 7.4 Run `make test` — all unit + e2e tests pass
- [x] 7.5 Run `make test-integration` — persistence tests pass against real PostgreSQL
- [x] 7.6 Run `make ci` — full gate green; compare against the baseline from task 1.1
- [x] 7.7 Update `CLAUDE.md`: kanban description updated to reflect RBAC guards; env-vars table notes the new TTL default; remove any references to `APP_WRITE_API_KEY` / `APP_WRITE_API_KEYS`
