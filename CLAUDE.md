# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
cp .env.example .env && uv sync
docker compose up -d db
uv run alembic upgrade head

# Development
make dev                          # run with auto-reload (FastAPI CLI)
make dev PORT=8080                # override port

# Quality
make format                       # Ruff formatter
make lint                         # Ruff lint
make lint-fix                     # Ruff lint with auto-fix
make lint-arch                    # Import Linter architecture contracts
make typecheck                    # mypy
make quality                      # lint + arch lint + typecheck

# Testing
make test                         # unit + e2e (no Docker)
make test-integration             # Docker-backed persistence tests
make test-e2e                     # end-to-end HTTP tests only
make test-feature FEATURE=kanban  # single feature
make test-feature FEATURE=auth    # single feature
make cov                          # tests + terminal coverage
make ci                           # full gate: quality + test + integration

# Migrations
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head

# Run single test file
uv run pytest src/features/kanban/tests/unit/domain/test_board.py
uv run pytest src/features/auth/tests/e2e/test_auth_flow.py

# Skip Docker in integration tests
KANBAN_SKIP_TESTCONTAINERS=1 make test-integration
```

## Architecture

Feature-first hexagonal architecture enforced by Import Linter contracts. Three active features: `auth`, `authorization`, and `kanban`. `src/features/_template` is an inert scaffold.

The three features communicate only through ports:

- **`auth`** owns identity: users, passwords, JWT issuance, refresh-token cookies, password reset, email verify, admin user/audit listings. It consumes nothing from authorization or kanban.
- **`authorization`** owns the ReBAC engine: the `AuthorizationPort`, the runtime `AuthorizationRegistry` other features register into, the SQLModel adapter, the SpiceDB stub, and `BootstrapSystemAdmin`. It consumes three small outbound ports (`UserAuthzVersionPort`, `UserRegistrarPort`, `AuditPort`) that auth implements.
- **`kanban`** owns boards, columns, and cards. It consumes only the `AuthorizationPort` (for checks and list filtering) and the registry (to declare its resource types at startup). Kanban never imports auth.

The cross-feature `relationships` table is platform-owned (`src/platform/persistence/sqlmodel/authorization/`) because every feature's authz check reads it at request time. The authorization feature is its only writer.

### Layer stack (inner → outer)

```
domain → application → adapters → composition
```

Each layer can only import from layers to its left. `platform` is cross-cutting but must never import `features`.

### Module map

| Module | Role |
|---|---|
| `src/main.py` | Composition root — mounts all feature routes and wires containers in the lifespan event |
| `src/platform/api/app_factory.py` | FastAPI factory: CORS, trusted hosts, docs, middleware, Problem Details handlers |
| `src/platform/config/settings.py` | `AppSettings` — pydantic-settings with `APP_` prefix; validates that production keys are set |
| `src/platform/shared/result.py` | `Result[T, E]` / `Ok` / `Err` — used by all use cases instead of exceptions |
| `src/platform/persistence/sqlmodel/authorization/models.py` | `RelationshipTable` — cross-feature ReBAC tuples; platform-owned because every feature reads it at request time |
| `src/features/kanban/` | Kanban board, column, and card CRUD |
| `src/features/authorization/` | ReBAC engine, `AuthorizationPort`, `AuthorizationRegistry`, `BootstrapSystemAdmin` |
| `src/features/auth/` | JWT auth, refresh-token cookies, rate limiting, admin user/audit endpoints |

### Auth feature (`src/features/auth/`)

Identity-only. Registration, login, refresh, password reset, email verify, principal resolution, and the admin endpoints that list auth's own state (`/admin/users`, `/admin/audit-log`). No authorization logic lives here.

- `application/use_cases/auth/*` — `RegisterUser`, `LoginUser`, `RotateRefreshToken`, `LogoutUser`, `RequestPasswordReset`, `ConfirmPasswordReset`, `RequestEmailVerification`, `ConfirmEmailVerification`, `ResolvePrincipalFromAccessToken`
- `application/use_cases/admin/*` — `ListUsers`, `ListAuditEvents` (the admin HTTP routes use the platform `require_authorization` dependency to gate on `system:main`)
- `application/rate_limit.py` — `FixedWindowRateLimiter` (in-process, single instance) and `RedisRateLimiter` (sliding window via Lua script, distributed); selected at startup based on `APP_AUTH_REDIS_URL`
- `application/jwt_tokens.py` — `AccessTokenService` (issue/decode JWT, cache principal by `authz_version`)
- `adapters/outbound/authz_version/` — `SQLModelUserAuthzVersionAdapter` (and its session-scoped variant): implements the authorization feature's `UserAuthzVersionPort`
- `adapters/outbound/user_registrar/` — `SQLModelUserRegistrarAdapter`: implements `UserRegistrarPort`
- `adapters/outbound/audit/` — `SQLModelAuditAdapter`: implements `AuditPort`
- Refresh tokens travel as `httpOnly` cookies scoped to `/auth`; access tokens are JWTs in response bodies
- Bootstrap: set `APP_AUTH_SEED_ON_STARTUP=true` + `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` to create an initial system-admin on startup (the bootstrap use case itself lives in the authorization feature)

### Authorization feature (`src/features/authorization/`)

Pure ReBAC concerns. Other features call into it through one port; it calls back through three small ports auth implements.

- `application/ports/authorization_port.py` — `AuthorizationPort` Protocol (`check`, `lookup_resources`, `lookup_subjects`, `write_relationships`, `delete_relationships`)
- `application/registry.py` — `AuthorizationRegistry`: features call `register_resource_type(...)` and `register_parent(...)` at startup; sealed by `main.py` before the app serves traffic
- `application/use_cases/bootstrap_system_admin.py` — `BootstrapSystemAdmin` (composes `UserRegistrarPort` + `AuthorizationPort` + `AuditPort`)
- `application/ports/outbound/` — `UserAuthzVersionPort` (cache invalidation), `UserRegistrarPort` (register-or-lookup for bootstrap), `AuditPort` (write `authz.*` events to auth's audit log)
- `adapters/outbound/sqlmodel/` — `SQLModelAuthorizationAdapter` (engine-owning) and `SessionSQLModelAuthorizationAdapter` (session-scoped, used by kanban's UoW)
- `adapters/outbound/spicedb/` — `SpiceDBAuthorizationAdapter` stub; one swap to drop in a real SpiceDB integration
- `composition/wiring.py` — `register_authorization_error_handlers(app)` maps `NotAuthorizedError` → 403 and `UnknownActionError` → 500

### Kanban feature (`src/features/kanban/`)

- `domain/` — pure Python: `Board` aggregate root owns ordered `Column` entities, each owning ordered `Card` entities; card movement/position logic lives here
- `application/` — commands/queries, `UnitOfWorkPort` and `KanbanQueryRepositoryPort` protocols, use cases return `Result`
- `adapters/outbound/persistence/sqlmodel/` — SQLModel tables (`boards`, `columns_`, `cards`); full aggregate snapshot writes; deferrable position-uniqueness constraints; optimistic concurrency via `boards.version`
- `adapters/inbound/http/` — routers split into read and write; mounted in `main.py` behind the platform-level `require_authorization` dependency
- `composition/wiring.py` — `register_kanban_authorization(registry, lookup)` declares the three kanban resource types (`kanban`, `column`, `card`), the `owner ⊇ writer ⊇ reader` hierarchy, and the `card → column → board` parent walk
- `composition/container.py` — `KanbanContainer` + `build_kanban_container(..., user_authz_version_factory=...)`; the factory closure lets `main.py` supply auth's session-scoped `UserAuthzVersionPort` without kanban importing auth

### Request flow

```
HTTP → RequestContextMiddleware (X-Request-ID) → FastAPI router
  → inbound adapter (Pydantic schemas → command/query)
  → use case (domain + outbound port)
  → Result[contract, ApplicationError]
  → inbound adapter (contract → Pydantic response schema, or HTTP error)
  → platform error_handlers → application/problem+json
```

### Layer contracts (Import Linter)

Contracts are defined in `pyproject.toml` under `[tool.importlinter]`. Key rules:
- `platform` → no `features` imports
- `domain` → no framework imports (FastAPI, SQLModel, Pydantic, Alembic, etc.)
- `application` → no adapter, FastAPI, SQLModel, SQLAlchemy, or Alembic imports
- `adapters.inbound` → no `adapters.outbound`, no `domain` directly, no SQL libraries
- `adapters.outbound` → no `adapters.inbound`, no use cases, no inbound ports
- `auth` ↛ `authorization` and `authorization` ↛ `auth` (production code; the two features communicate only through `authorization/application/ports/outbound`)
- `kanban` ↛ `auth` (production code)

Run boundary checks: `make lint-arch`

## Adding a new feature

A new feature that authorizes anything plugs into the authorization registry from its own composition root. Concrete steps:

1. Mirror the `src/features/_template` directory layout under `src/features/<name>/`.
2. Decide which resource types your feature owns. For each *leaf* type (one whose tuples will live in the `relationships` table), call `registry.register_resource_type("<type>", actions={...}, hierarchy={...})` from your feature's wiring module. For each *inherited* type (delegates to a parent via a lookup), call `registry.register_parent("<type>", parent_of=..., inherits_from="<parent>")`.
3. Build your feature's container in `main.py` after the authorization container exists; pass `authorization.port` and `authorization.registry` in.
4. Gate your HTTP routes with the platform-level `require_authorization("<action>", "<resource_type>", id_loader=...)` dependency.
5. If the feature needs the authorization tuple write to commit atomically with its own DB writes, take a `user_authz_version_factory` parameter on its container the same way kanban does and pass it to the unit-of-work.
6. No feature should import another feature's modules; cross-feature work goes through `authorization` ports.

## Testing strategy

| Scope | Marker | Location | Notes |
|---|---|---|---|
| Unit | `unit` | `*/tests/unit/` | Pure logic, no IO; uses fakes from `*/tests/fakes/` |
| End-to-end | `e2e` | `*/tests/e2e/` | HTTP flows through FastAPI with in-memory fakes |
| Contract | (called by unit/integration) | `*/tests/contracts/` | Same behavior assertions run against fake and real adapters |
| Integration | `integration` | `*/tests/integration/` | Requires Docker/testcontainers; hits real PostgreSQL |

## Coding conventions

- Use cases return `Result[T, ApplicationError]`, never raise through the application layer.
- `@dataclass(slots=True)` for use cases and mutable domain entities; `@dataclass(frozen=True, slots=True)` for immutable commands/queries/contracts.
- FastAPI dependencies are declared as `Annotated` type aliases (see existing `*Dep` names in `adapters/inbound/http/dependencies.py`).
- Feature HTTP errors map application errors to HTTP status codes in `adapters/inbound/http/errors.py`; the platform renders the final Problem Details response.
- New feature code goes under `src/features/<feature_name>/` mirroring the `_template` scaffold.
- New migrations: update SQLModel tables first, then `uv run alembic revision --autogenerate -m "..."`.

## Production checklist

The settings validator (`_validate_production_settings` in `settings.py`) will refuse to start if:
- `APP_AUTH_JWT_SECRET_KEY` is unset
- `APP_CORS_ORIGINS` contains `*`
- `APP_AUTH_COOKIE_SECURE` is `False`
- `APP_ENABLE_DOCS` is `True`

Set `APP_ENVIRONMENT=production` to activate these checks.

## Key env vars (auth-related, beyond README)

| Variable | Default | Purpose |
|---|---|---|
| `APP_AUTH_JWT_SECRET_KEY` | unset | Required in production; signs all JWTs |
| `APP_AUTH_SEED_ON_STARTUP` | `false` | Seeds RBAC roles/permissions on startup |
| `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` | unset | Creates initial super-admin if both are set |
| `APP_AUTH_RETURN_INTERNAL_TOKENS` | `false` | Exposes single-use tokens in responses — only for e2e tests |
| `APP_AUTH_REDIS_URL` | unset | Enables distributed Redis rate limiter; falls back to in-process if unset |
| `APP_AUTH_RATE_LIMIT_ENABLED` | `true` | Enables/disables auth rate limiting |
| `APP_AUTH_RBAC_ENABLED` | `true` | Enables RBAC permission checks |
| `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS` | `5` | Bounds the worst-case revocation lag for cached principals. Lower values reduce lag but increase DB/cache load on each request; raise it for high-throughput deployments where a longer lag is acceptable. |
