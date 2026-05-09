## Context

Verification against the codebase (2026-05-09) showed the original proposal was based on several stale premises. This design records the corrected scope and the reasoning behind each remaining decision.

**What is already correct in the codebase (and therefore NOT in scope):**

- Outbound auth ports (`UserRepositoryPort`, `TokenRepositoryPort`, `RBACRepositoryPort`, `AuditRepositoryPort`, `AuthRepositoryPort`) — already present in `auth/application/ports/outbound/auth_repository.py` with proper ISP slicing.
- `APP_AUTH_JWT_AUDIENCE` setting — already exists (`settings.py:59`) and is required in production (`settings.py:129-130`).
- `APP_AUTH_RBAC_ENABLED` production validation — already enforced (`settings.py:140-141`).
- Distributed-rate-limiter startup assertion — already raises in `container.py:124-128` and validates in `settings.py:142-148`.
- `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS` configurability — already a setting (`settings.py:94`); only the default value is wrong.

**What this change addresses:**

1. `Principal` lives in `auth/application/types.py`; kanban can't import it without crossing the cross-feature boundary, so kanban currently sidesteps the contract by reading `request.state.actor_id` only.
2. Kanban routes are guarded by plain JWT (`main.py:96-101`) — no permission check.
3. `X-API-Key` infrastructure (`platform/api/dependencies/security.py`, `write_api_key` settings, e2e tests with `secured_client`) exists but is **not** wired into kanban from `main.py`. It is dead code that teaches a weaker alternative to RBAC.
4. Default principal cache TTL is 30 seconds — too long for a starter-template default.
5. Auth has no application-layer use-case unit tests.

**Sequencing:** This change depends on `hexagonal-architecture-refactor` landing first. That change introduces:
- per-use-case `@dataclass(slots=True)` classes (`RegisterUser`, `LoginUser`, `RefreshToken`, `AssignRole`, `GrantPermission`, ...) — the targets of `auth-unit-tests`
- inbound port protocols
- `Result[T, AuthError]` at the application boundary
- typed `RequestState` (which the principal-contract factory will write into via `set_actor_id`)

If `hexagonal-architecture-refactor` is delayed, the auth-unit-tests capability of this change MUST also be deferred.

## Goals / Non-Goals

**Goals:**
- Move `Principal` and the authorization helpers to `platform/shared/` so features have a stable, contract-only import target.
- Introduce a `require_permissions(...)` dependency at the platform level and use it on kanban.
- Seed `kanban:read` and `kanban:write` and assign them to the standard roles.
- Delete the unused `X-API-Key` write infrastructure.
- Lower the principal cache TTL default from 30 to 5 seconds.
- Add use-case-level unit tests for the new per-use-case classes.

**Non-Goals:**
- Introducing an `AuthProviderPort` facade (per-use-case classes already serve as inbound ports — see `hexagonal-architecture-refactor`).
- Introducing new outbound port protocols — they already exist.
- Adding new env vars / settings (`APP_AUTH_JWT_AUDIENCE`, `APP_AUTH_RBAC_ENABLED` validation, distributed-rate-limit assertion are all already in place).
- Implementing any external auth provider (Supabase, Clerk, Cognito, OAuth) — out of scope.
- Implementing any alternative persistence backend.
- Adding multi-tenancy or resource-level ownership checks.
- Replacing SQLModel or modifying migrations.
- Changing the public HTTP API or response schemas.

## Decisions

### Decision 1: `Principal` moves to `platform/shared/principal.py` with the existing field set
**Choice:** Define `@dataclass(frozen=True, slots=True) Principal` in `src/platform/shared/principal.py` with the seven fields currently in `auth/application/types.py`: `user_id: UUID`, `email: str`, `is_active: bool`, `is_verified: bool`, `authz_version: int`, `roles: frozenset[str]`, `permissions: frozenset[str]`. The auth feature imports it from there. Kanban and future features also import it from there.
**Rationale:** Import Linter forbids cross-feature imports. Platform is the legal shared location. The dataclass has no auth-specific logic — it is a read contract. Keeping the existing field set means zero behavior change; flattening or renaming would be an unrelated refactor.
**Alternative considered:** Re-export from `auth/__init__.py`. Rejected — Import Linter would still flag kanban's import.

### Decision 2: `require_permissions` is exposed at the platform level
**Choice:** Move `require_permissions`, `require_any_permission`, and `require_roles` from `auth/adapters/inbound/http/dependencies.py` to a platform-level module (e.g., `platform/api/authorization.py`). They take a `Principal` (now from platform) and consult `principal.permissions` / `principal.roles`. The `auth_rbac_enabled` bypass logic stays in the dependency body (it consults `AuthContainer.settings`).
**Rationale:** These functions are pure permission checks parameterised by the principal contract. They don't need to live in auth — only the principal *resolution* (turning a JWT into a `Principal`) belongs in auth.
**Alternative considered:** Keep them in auth and have kanban import from `auth/__init__.py`. Rejected — same Import Linter concern.

### Decision 3: `Principal` resolver stays in auth; platform exposes the factory
**Choice:** `platform/shared/authorization.py` (or `platform/api/authorization.py` if FastAPI imports are involved) exposes `build_principal_dependency(resolver) -> Callable`. The `resolver` is supplied by auth (it's the new `ResolvePrincipalFromAccessTokenPort` use case that `hexagonal-architecture-refactor` introduces). `build_principal_dependency` reads the bearer token, calls the resolver, sets `request.state.actor_id` (via the typed `set_actor_id` helper from the same change), and returns the `Principal`.
**Rationale:** Composition root pattern: auth supplies the resolver at startup; platform packages it as a FastAPI dependency.
**Alternative considered:** Put the dependency in `platform/shared/`. If `platform/shared/` is forbidden from importing FastAPI by Import Linter, the FastAPI-aware wrapper goes in `platform/api/`; the framework-agnostic resolver `Protocol` stays in `platform/shared/`.

### Decision 4: Kanban uses RBAC, X-API-Key is deleted entirely
**Choice:** Remove all X-API-Key infrastructure (`platform/api/dependencies/security.py`, `write_api_key` settings, e2e tests, `.env.example` entries). Update `main.py` to pass `read_dependencies=[require_permissions("kanban:read")]` and `write_dependencies=[require_permissions("kanban:write")]`. Seed both permissions on `super_admin`/`admin` and grant them to `user` so the default registered user can use the kanban demo.
**Rationale:** The X-API-Key path is dead code: `main.py` never wires it. Keeping it would teach a weaker alternative to RBAC. Granting `kanban:write` to `user` matches the demo intent (users in this template *do* drive boards).
**Alternative considered:** Restrict `kanban:write` to `manager`/`admin` only. Rejected for the demo: the point of the kanban feature is for any registered user to use it, while showing how RBAC gates the route.
**Migration note:** No existing client uses X-API-Key on kanban (it was never mounted), so this is a code cleanup, not a behavior change.

### Decision 5: TTL default change is the entire scope of `security-hardening`
**Choice:** Lower `auth_principal_cache_ttl_seconds` default from 30 to 5 in `AppSettings`; lower the `InProcessPrincipalCache.create(maxsize=1000, ttl=30)` fallback to `ttl=5`. Update any settings tests that pinned the default.
**Rationale:** The original spec proposed adding `APP_AUTH_JWT_AUDIENCE`, `APP_AUTH_RBAC_ENABLED` production validation, and distributed-rate-limiter assertions — all already implemented. The only real gap is the default value. 5 seconds is short enough to keep the lag from being a footgun, long enough to absorb burst traffic into the cache.
**Alternative considered:** Default to 0 (disable cache by default). Rejected — would make the integration tests covering the cache path harder to express; 5s is the better template default.

### Decision 6: Auth unit tests target the per-use-case classes
**Choice:** Tests exercise the use-case classes introduced by `hexagonal-architecture-refactor` (`RegisterUser`, `LoginUser`, `RefreshToken`, `AssignRole`, `GrantPermission`) using `FakeAuthRepository` (implementing the existing `AuthRepositoryPort` or its narrower sub-protocols), `FakeClock`, and `FakeIdGenerator`. No mocking framework.
**Rationale:** Consistent with kanban's testing strategy. Fakes are transparent, debuggable, and serve as executable documentation of the port contract. Aligning the fake with the existing port (rather than introducing a new `UserRepositoryPort`/`RefreshTokenStorePort` pair) avoids duplicating the persistence contract.
**Alternative considered:** `unittest.mock.Mock`. Rejected — couples tests to method names instead of behavior.

## Risks / Trade-offs

**[Risk] Moving `Principal` to platform forces every internal import in auth to update.**
→ Mitigation: keep a transitional alias `Principal = PlatformPrincipal` in `auth/application/types.py` for one commit; remove after all internal callers have moved. Verify with `grep -rn "from src.features.auth.application.types import Principal" src/` returning zero before deleting the alias.

**[Risk] Granting `kanban:write` to the `user` role surprises operators upgrading.**
→ Mitigation: document in `CLAUDE.md` and the migration plan. Re-seed is idempotent; existing deployments simply gain the permissions on next startup with `APP_AUTH_SEED_ON_STARTUP=true`.

**[Risk] Lowering TTL to 5s increases DB/cache load.**
→ Mitigation: still configurable; document tradeoff in `CLAUDE.md`. 5s amortises across burst traffic and bounds revocation lag.

**[Risk] Auth unit tests depend on `hexagonal-architecture-refactor` landing first.**
→ Mitigation: this change explicitly sequences after the refactor. If sequencing breaks down, the auth-unit-tests capability can be deferred without affecting the others.

**[Risk] Deleting `X-API-Key` test fixtures breaks any local script using them.**
→ Mitigation: those scripts already do not work end-to-end (the dep was never mounted in main.py). Document in commit message.

## Migration Plan

1. **Prerequisite**: `hexagonal-architecture-refactor` is merged. Run `make ci` to confirm baseline is green.
2. **Platform principal contract** (lowest blast radius):
   a. `platform/shared/principal.py` — add `Principal` with the existing field set.
   b. `platform/shared/authorization.py` (or `platform/api/authorization.py`) — add `build_principal_dependency`, `require_permissions`, `require_roles`, `require_any_permission`.
   c. Auth's `application/types.py` — add transitional `Principal = PlatformPrincipal` alias.
   d. Auth's HTTP dependencies — switch internal imports to platform; remove the local helpers (re-export from platform if needed for adapter call sites).
   e. Auth's bootstrap and `set_actor_id` use the typed helper from `hexagonal-architecture-refactor`.
   f. Run `make lint-arch` and `make typecheck`.
3. **Kanban RBAC**:
   a. `seed.py` — add `kanban:read` and `kanban:write`; assign to roles per the spec.
   b. `main.py` — `read_dependencies=[require_permissions("kanban:read")]`, `write_dependencies=[require_permissions("kanban:write")]`.
   c. Update kanban e2e fixtures so the test JWT issues a `Principal` with both permissions.
   d. Run `make test-e2e`.
4. **Delete X-API-Key infrastructure**:
   a. Remove `platform/api/dependencies/security.py`.
   b. Remove `write_api_key` / `write_api_keys` from `AppSettings`; remove `.env.example` entries.
   c. Delete `kanban/tests/e2e/test_write_api_key_auth.py`; remove `secured_settings`/`secured_client` from `conftest.py`.
   d. Run `make test`.
5. **Lower TTL default**:
   a. `AppSettings.auth_principal_cache_ttl_seconds` default `30` → `5`.
   b. `InProcessPrincipalCache.create(...)` `ttl: int = 30` → `ttl: int = 5`.
   c. Update settings test that pins the default.
6. **Auth unit tests**:
   a. `tests/fakes/` — `FakeAuthRepository`, `FakeClock`, `FakeIdGenerator`.
   b. `tests/unit/test_register_user.py`, `test_login_user.py`, `test_refresh_token.py`, `test_assign_role.py`, `test_grant_permission.py`.
   c. Run `make test-feature FEATURE=auth`.
7. **Final gate**: `make ci`.
8. **Rollback**: each step is independently revertible; no DB migrations.

## Open Questions

- Should `kanban:write` be granted to `user` by default, or only `kanban:read`? **Leaning grant both** — the kanban feature exists as a working demo and gating writes behind a manual permission grant adds friction for template users. Documented in Decision 4.
- Should the transitional `Principal` alias in `auth/application/types.py` be removed in the same change or in a follow-up? **Leaning same change**, with a final grep gate; the field set is identical so no caller-visible change occurs.
