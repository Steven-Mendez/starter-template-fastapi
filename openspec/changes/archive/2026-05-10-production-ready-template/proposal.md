## Why

The starter template's two features are architecturally sound individually, but they don't yet demonstrate the full pattern a production team needs. Verification against the current codebase (2026-05-09) narrows the real gaps to four:

1. **Kanban has no real RBAC.** `src/main.py:96-101` guards every kanban route with `Depends(get_current_principal)` (plain JWT) — no permission check. The `X-API-Key` infrastructure that exists in `src/platform/api/dependencies/security.py` is never wired into kanban routes from `main.py`; it teaches the wrong pattern and should be removed.
2. **`Principal` and the authorization helpers live inside `auth` internals** (`src/features/auth/application/types.py` and `auth/adapters/inbound/http/dependencies.py`). Any feature that needs to identify the current user must import from auth internals, which Import Linter's cross-feature contract prohibits — the only reason kanban gets away with it today is by reading `request.state.actor_id` and never looking at the principal directly.
3. **The principal cache TTL default is 30 seconds**, which means up to a 30-second permission-revocation lag in the default deployment. The setting is already configurable; what's missing is a sane default.
4. **The auth application layer has no use-case unit tests.** The `tests/unit/` folder contains crypto, JWT, rate-limiter, and HTTP mapping tests but nothing that exercises registration, login, refresh rotation, or RBAC behavior in isolation — coverage that the per-use-case decomposition introduced by `hexagonal-architecture-refactor` is intended to enable.

This change is sequenced **after** `hexagonal-architecture-refactor`: it depends on the per-use-case classes and inbound ports that change introduces (the auth-unit-tests capability targets those classes by name).

## What Changes

- **Move `Principal` to `src/platform/shared/principal.py`** — preserve the exact field set already in `auth/application/types.py` (`user_id: UUID`, `email: str`, `is_active: bool`, `is_verified: bool`, `authz_version: int`, `roles: frozenset[str]`, `permissions: frozenset[str]`). Add `build_principal_dependency(...)` factory plus a typed `require_permissions(...)` exposed at the platform level so any feature can depend on the current user without importing from auth internals.
- **Upgrade kanban from plain JWT to RBAC** — seed `kanban:read` and `kanban:write` permissions in `auth/application/seed.py`, assign them to the standard roles, and update `main.py` to mount kanban with `read_dependencies=[require_permissions("kanban:read")]` and `write_dependencies=[require_permissions("kanban:write")]`.
- **Remove the unused `X-API-Key` infrastructure** — delete `src/platform/api/dependencies/security.py`, the `write_api_key` / `write_api_keys` settings, the matching e2e tests and fixtures, and the `.env.example` entries. The path is replaced by RBAC, so leaving the dual code path teaches a misleading alternative.
- **Lower the principal cache TTL default from 30 to 5 seconds** — change the `AppSettings.auth_principal_cache_ttl_seconds` default and the `InProcessPrincipalCache.create(...)` `ttl=30` fallback to `5`. The env var name and consumers are unchanged.
- **Add auth use-case unit tests** — `FakeAuthRepository` (implementing the existing outbound port protocols), `FakeClock`, `FakeIdGenerator`, and unit tests for `RegisterUser`, `LoginUser`, `RefreshToken`, `AssignRole`, `GrantPermission` (the per-use-case classes introduced by `hexagonal-architecture-refactor`).

## Capabilities

### New Capabilities

- `platform-principal-contract`: Stable `Principal` type and authorization-dependency factory in `platform/shared/` so any feature imports the current-user contract from platform, not from auth.
- `kanban-rbac`: `kanban:read` / `kanban:write` permissions seeded in RBAC; kanban HTTP routes guarded by `require_permissions(...)` from the platform contract; the unused `X-API-Key` write-key infrastructure is removed.
- `security-hardening`: Lower the default principal cache TTL from 30 to 5 seconds (the setting itself was already configurable).
- `auth-unit-tests`: Per-use-case unit tests against the new `RegisterUser`/`LoginUser`/`RefreshToken`/RBAC classes using in-memory fakes that implement the existing outbound port protocols.

### Modified Capabilities

*(No existing spec-level behavior changes — all public HTTP APIs are preserved. The `X-API-Key` write protection on kanban routes was an unwired code path; removing it has no production effect.)*

## Impact

- `src/platform/shared/` — gains `principal.py` and `authorization.py` (or split: framework-agnostic types in `shared/`, FastAPI-bound `require_permissions` in `platform/api/`).
- `src/features/auth/application/types.py` — `Principal` is removed (or temporarily re-exported during migration); auth callers import from platform.
- `src/features/auth/application/seed.py` — gains `kanban:read` / `kanban:write` in `ALL_PERMISSIONS` and `ROLE_PERMISSIONS`.
- `src/features/auth/adapters/inbound/http/dependencies.py` — `Principal` import migrates to platform; `require_permissions`/`require_roles`/`require_any_permission` are re-exported from platform (or thin wrappers around platform helpers).
- `src/main.py` — `read_dependencies` and `write_dependencies` for `mount_kanban_routes` switch from `[Depends(get_current_principal)]` to `[require_permissions("kanban:read")]` / `[require_permissions("kanban:write")]`.
- `src/platform/api/dependencies/security.py` — **deleted**.
- `src/platform/config/settings.py` — `write_api_key` / `write_api_keys` fields removed; `auth_principal_cache_ttl_seconds` default changes from `30` to `5`.
- `src/features/auth/application/cache.py:49` — `InProcessPrincipalCache.create(maxsize=1000, ttl=30)` → `ttl=5`.
- `src/features/auth/tests/fakes/` — new package: `FakeAuthRepository`, `FakeClock`, `FakeIdGenerator`.
- `src/features/auth/tests/unit/` — new test modules covering register/login/refresh/RBAC.
- `src/features/kanban/tests/e2e/test_write_api_key_auth.py` — **deleted** (along with `secured_settings`/`secured_client` fixtures in `conftest.py`).
- `.env.example` — `APP_WRITE_API_KEY` / `APP_WRITE_API_KEYS` entries removed.
- Import Linter contracts — no contract relaxations required; the kanban-imports-platform edge already exists.
- Public HTTP API — no breaking changes. (Internal: kanban routes now require the principal to hold `kanban:read` / `kanban:write`; users seeded by `auth_seed_on_startup` already receive these.)
- **Out of scope (handled by `hexagonal-architecture-refactor`):** decomposing `AuthService`/`RBACService` into per-use-case classes, inbound port protocols, `Result[T, AuthError]` adoption, deletion of `services.py` shim, `make_auth_guard()` helper, typed `RequestState`. This change depends on those classes being in place.
