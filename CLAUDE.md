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

Feature-first hexagonal architecture enforced by Import Linter contracts. Two active features: `kanban` and `auth`. `src/features/_template` is an inert scaffold.

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
| `src/features/kanban/` | Kanban board, column, and card CRUD |
| `src/features/auth/` | JWT auth, refresh-token cookies, RBAC, rate limiting, admin API |

### Auth feature (`src/features/auth/`)

Unlike kanban (which uses strict hexagonal ports), auth uses a flatter service model:

- `application/services.py` — `AuthService` (register, login, refresh, password reset, email verify) and `RBACService` (roles, permissions, assignments); both record audit events and bump `authz_version` on permission changes
- `application/rate_limit.py` — `FixedWindowRateLimiter` (in-process, single instance) and `RedisRateLimiter` (sliding window via Lua script, distributed); selected at startup based on `APP_AUTH_REDIS_URL`
- `application/jwt_tokens.py` — `AccessTokenService` (issue/decode JWT, cache principal by `authz_version`)
- `adapters/inbound/http/auth.py` — public routes under `/auth` (register, login, refresh, logout, me, password reset, email verify)
- `adapters/inbound/http/admin.py` — admin routes under `/admin` guarded by RBAC `require_permissions` dependency
- `composition/container.py` — `AuthContainer` dataclass wiring all collaborators
- Refresh tokens travel as `httpOnly` cookies scoped to `/auth`; access tokens are JWTs in response bodies
- Seeded RBAC roles: `super_admin`, `admin`, `manager`, `user` (see `application/seed.py`)
- Bootstrap: set `APP_AUTH_SEED_ON_STARTUP=true` + `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` to create an initial super-admin on startup

### Kanban feature (`src/features/kanban/`)

- `domain/` — pure Python: `Board` aggregate root owns ordered `Column` entities, each owning ordered `Card` entities; card movement/position logic lives here
- `application/` — commands/queries, `UnitOfWorkPort` and `KanbanQueryRepositoryPort` protocols, use cases return `Result`
- `adapters/outbound/persistence/sqlmodel/` — SQLModel tables (`boards`, `columns_`, `cards`); full aggregate snapshot writes; deferrable position-uniqueness constraints; optimistic concurrency via `boards.version`
- `adapters/inbound/http/` — routers split into read and write; mounted in `main.py` behind `require_permissions("kanban:read")` / `require_permissions("kanban:write")` from the platform authorization helpers
- `composition/` — `KanbanContainer` + wiring helpers

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
- Features must not import each other

Run boundary checks: `make lint-arch`

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
