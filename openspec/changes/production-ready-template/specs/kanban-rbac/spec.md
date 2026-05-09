## ADDED Requirements

### Requirement: Kanban permissions are seeded for all standard roles
The RBAC seed data SHALL include `kanban:read` and `kanban:write` permissions registered in `src/features/auth/application/seed.py` (`ALL_PERMISSIONS` and `ROLE_PERMISSIONS`). Role assignments:

- `super_admin` — both (already implicit, since super_admin receives `set(ALL_PERMISSIONS)`)
- `admin` — both
- `manager` — `kanban:read` only
- `user` — `kanban:read` and `kanban:write` (so the default registered user can use the kanban demo without an admin escalation)

All seeded permissions SHALL be idempotent (re-seeding does not create duplicates — relies on existing seed-by-name behavior).

#### Scenario: Seed creates kanban permissions on startup
- **WHEN** `APP_AUTH_SEED_ON_STARTUP=true` and the application starts for the first time
- **THEN** `kanban:read` and `kanban:write` permissions exist in the database with descriptions

#### Scenario: Re-seeding does not duplicate permissions
- **WHEN** the application restarts with `APP_AUTH_SEED_ON_STARTUP=true` and permissions already exist
- **THEN** the permission count for `kanban:*` remains unchanged

#### Scenario: Default user role has kanban:read and kanban:write
- **WHEN** a new user is registered and assigned the `user` role
- **THEN** their resolved `Principal` includes both `kanban:read` and `kanban:write` in the permissions set

### Requirement: Kanban routes upgrade from plain JWT to RBAC permission checks
**Current state:** `src/main.py` mounts kanban with `read_dependencies=write_dependencies=[Depends(get_current_principal)]` — both are guarded by JWT only, with no permission check. The `X-API-Key` infrastructure in `src/platform/api/dependencies/security.py` exists but is **not** wired into kanban routes from `main.py`.

**Required change:** `src/main.py` (or `mount_kanban_routes` callers) SHALL pass `read_dependencies=[require_permissions("kanban:read")]` and `write_dependencies=[require_permissions("kanban:write")]`, where `require_permissions` is sourced from the platform principal contract (see `platform-principal-contract`).

Requests reaching kanban routes SHALL be rejected as follows:

- No `Authorization` header → HTTP 401
- Authenticated but missing the required permission → HTTP 403
- Authenticated and holding the required permission → handler executes

#### Scenario: Authenticated user with kanban:read accesses board list
- **WHEN** `GET /api/boards` is called with a valid JWT from a user holding `kanban:read`
- **THEN** the response is HTTP 200

#### Scenario: Authenticated user without kanban:read is rejected
- **WHEN** `GET /api/boards` is called with a valid JWT from a user whose principal lacks `kanban:read`
- **THEN** the response is HTTP 403

#### Scenario: Authenticated user with kanban:read but not kanban:write cannot write
- **WHEN** `POST /api/boards` is called with a valid JWT from a user holding only `kanban:read`
- **THEN** the response is HTTP 403

#### Scenario: Unauthenticated request is rejected
- **WHEN** `GET /api/boards` is called with no Authorization header
- **THEN** the response is HTTP 401

### Requirement: Platform write-API-key dependency is removed
Because kanban no longer uses `X-API-Key` for write protection (and never relied on it post-refactor), the platform-level write-key infrastructure SHALL be removed:

- Delete `src/platform/api/dependencies/security.py` (`require_write_api_key`, `WriteApiKeyDep`, `RequireWriteApiKey`)
- Remove `write_api_key: str | None` and `write_api_keys: list[str]` from `AppSettings`
- Remove `APP_WRITE_API_KEY` / `APP_WRITE_API_KEYS` from `.env.example`
- Delete `src/features/kanban/tests/e2e/test_write_api_key_auth.py` and the `secured_settings`/`secured_client` fixtures in `kanban/tests/e2e/conftest.py`

#### Scenario: Write-key module is gone
- **WHEN** `find src/platform -name "security.py"` is run
- **THEN** zero matches are returned

#### Scenario: Write-key settings are gone
- **WHEN** `grep -n "write_api_key" src/platform/config/settings.py` is run
- **THEN** zero matches are returned

#### Scenario: X-API-Key header has no effect on kanban writes
- **WHEN** `POST /api/boards` is called with a valid JWT lacking `kanban:write` AND a `X-API-Key: secret` header
- **THEN** the response is HTTP 403 (the API key is ignored entirely)

### Requirement: Kanban routes do not import from auth internals
Kanban HTTP adapter modules SHALL NOT import from `src/features/auth/`. The `require_permissions` dependency SHALL be imported from the platform principal contract (`src/platform/shared/authorization` or its FastAPI-bound counterpart in `platform/api/`).

#### Scenario: No auth imports in kanban
- **WHEN** `grep -rn "from src.features.auth" src/features/kanban/` is run
- **THEN** zero matches are returned

#### Scenario: Import Linter confirms isolation
- **WHEN** `make lint-arch` is run
- **THEN** zero violations are reported for the kanban feature importing from auth
