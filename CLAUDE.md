# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
cp .env.example .env && uv sync
docker compose up -d db
uv run alembic upgrade head

# Development
make dev                                  # run with auto-reload (FastAPI CLI)
make dev PORT=8080                        # override port
make worker                               # build the worker scaffold (no job runtime wired; exits non-zero until AWS SQS + Lambda, a later roadmap step)

# Quality
make format                               # Ruff formatter
make lint                                 # Ruff lint
make lint-fix                             # Ruff lint with auto-fix
make lint-arch                            # Import Linter architecture contracts
make typecheck                            # mypy
make quality                              # lint + arch lint + typecheck

# Testing
make test                                 # unit + e2e (no Docker)
make test-integration                     # Docker-backed persistence tests
make test-e2e                             # end-to-end HTTP tests only
make test-feature FEATURE=authentication  # single feature
make test-feature FEATURE=users           # single feature
make cov                                  # tests + coverage (gates line 80% + branch 60%)
make ci                                   # full gate: quality + cov + integration

# Migrations
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head

# Operational CLI (src/cli/ — composition-root peers of main.py/worker.py)
PYTHONPATH=src uv run python -m cli.create_super_admin create-super-admin --email <e> --password-env <ENVVAR>
                                          # create/promote the first system:main#admin; on-demand alternative to the APP_AUTH_SEED_ON_STARTUP bootstrap (--password-env names the var holding the password; promoting an existing account needs APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true)
make outbox-prune                         # one-shot prune of terminal outbox rows + stale dedup marks (same PruneOutbox code path as the worker prune cron; ignores APP_OUTBOX_ENABLED)

# Run single test file
uv run pytest src/features/authentication/tests/e2e/test_auth_flow.py
uv run pytest src/features/users/tests/unit/test_user_authz_version_adapter.py

# Skip Docker in integration tests
KANBAN_SKIP_TESTCONTAINERS=1 make test-integration
```

## Architecture

Feature-first hexagonal architecture enforced by Import Linter contracts.
Seven features ship out of the box. New features are created from scratch
following the layer stack and per-feature conventions documented below.

| Feature | Role |
|---|---|
| `authentication` | JWT issuance, login/logout/refresh, password reset, email verify, rate limiting, principal resolution, `credentials` table |
| `users` | The `User` entity, registration, profile, deactivation, admin user listing, `UserPort` |
| `authorization` | ReBAC engine, `AuthorizationPort`, `AuthorizationRegistry`, SQLModel adapter, `BootstrapSystemAdmin` |
| `email` | `EmailPort`, console adapter (dev/test; production email arrives with AWS SES at a later roadmap step), `EmailTemplateRegistry` |
| `background_jobs` | `JobQueuePort`, the `in_process` adapter (only shipped adapter; production job runtime — AWS SQS + a Lambda worker — arrives at a later roadmap step), `JobHandlerRegistry`, runtime-agnostic worker scaffold |
| `file_storage` | `FileStoragePort`, local + S3 (`boto3`) adapters |
| `outbox` | `OutboxPort`, the `outbox_messages` table, `SessionSQLModelOutboxAdapter`, `DispatchPending` relay use case (runs in the worker only) |

Cross-feature communication goes through ports only:

- `authentication` consumes `UserPort` (from `users`), `EmailPort`, `JobQueuePort`, and `AuthorizationPort`. It never imports another feature's adapters directly.
- `users` implements `UserRegistrarPort` and `UserAuthzVersionPort` for `authorization`. It doesn't import `authentication`.
- `authorization` consumes `UserRegistrarPort` + `UserAuthzVersionPort` (from `users`) and `AuditPort` (from `authentication`). It never imports either feature directly.
- `email`, `background_jobs`, and `file_storage` have no feature imports at all — features contribute templates/handlers through registries and call ports.

The cross-feature `relationships` table is platform-owned
(`src/app_platform/persistence/sqlmodel/authorization/`) because every feature's
authz check reads it at request time. The authorization feature is its only
writer.

### Layer stack (inner → outer)

```
domain → application → adapters → composition
```

Each layer can only import from layers to its left. `platform` is cross-cutting
but must never import `features` — except `app_platform.config.settings`, the
configuration composition root, which aggregates per-feature settings classes
with an explicit Import Linter exception.

### Module map

| Module | Role |
|---|---|
| `src/main.py` | Composition root — mounts every feature's routes and wires containers in the lifespan event |
| `src/worker.py` | Runtime-agnostic worker composition-root scaffold — loads the same composition root, registers handlers, collects cron descriptors, then exits non-zero (no job runtime is wired until AWS SQS + a Lambda worker, a later roadmap step) |
| `src/app_platform/api/app_factory.py` | FastAPI factory: CORS, trusted hosts, docs, middleware, Problem Details handlers |
| `src/app_platform/config/settings.py` | `AppSettings` — `APP_`-prefixed pydantic-settings; exposes typed per-feature views (`settings.email`, `settings.authentication`, …); aggregates per-feature production validation |
| `src/app_platform/config/sub_settings.py` | `DatabaseSettings`, `ApiSettings`, `ObservabilitySettings` — cross-cutting platform projections |
| `src/app_platform/shared/result.py` | `Result[T, E]` / `Ok` / `Err` — used by every use case |
| `src/app_platform/persistence/sqlmodel/authorization/models.py` | `RelationshipTable` — cross-feature ReBAC tuples |
| `src/features/<feature>/composition/settings.py` | Each feature owns a typed settings projection and its own `validate_production(errors)` method |

### Authentication feature (`src/features/authentication/`)

Credential and session shaped only. Registration writes through a
session-scoped `UserRegistrarPort` adapter inside the registration
transaction so the `User` row, the `Credential` row, and the
`auth.user_registered` audit event commit atomically; password-reset
and email-verification confirmations follow the same single-transaction
pattern (`internal_token_transaction()` covers the token consumption,
credential upsert / `mark_user_verified`, and audit event).

- `application/use_cases/auth/*` — `RegisterUser`, `LoginUser`, `RotateRefreshToken`, `LogoutUser`, `RequestPasswordReset`, `ConfirmPasswordReset`, `RequestEmailVerification`, `ConfirmEmailVerification`, `ResolvePrincipalFromAccessToken`
- `application/use_cases/admin/*` — `ListAuditEvents` (the admin HTTP routes use the platform `require_authorization` dependency to gate on `system:main`)
- `application/rate_limit.py` — `FixedWindowRateLimiter` (in-process) and `RedisRateLimiter` (sliding window); selected at startup based on `APP_AUTH_REDIS_URL`
- `application/jwt_tokens.py` — `AccessTokenService` (issue/decode JWT, cache principal by `authz_version`)
- `adapters/outbound/persistence/sqlmodel/models.py` — `CredentialTable` (`user_id`, `algorithm`, `hash`, …); unique on `(user_id, algorithm)`
- `adapters/outbound/audit/` — `SQLModelAuditAdapter`: implements authorization's `AuditPort`
- `composition/container.py` — takes `users.UserPort`, `jobs.JobQueuePort`, and the engine repository
- `composition/settings.py` — `AuthenticationSettings` projection with its own `validate_production`
- `email_templates/` — registers password-reset and email-verify templates with the email feature's `EmailTemplateRegistry` at startup
- Refresh tokens travel as `httpOnly` cookies scoped to `/auth`; access tokens are JWTs in response bodies
- Bootstrap: set `APP_AUTH_SEED_ON_STARTUP=true` + `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` to create an initial system-admin on startup (the use case itself lives in the authorization feature)

### Users feature (`src/features/users/`)

Owns the `User` entity and its lifecycle.

- `application/ports/user_port.py` — `UserPort` Protocol (`get_by_id`, `get_by_email`, `create`, `update_profile`, `deactivate`)
- `application/use_cases/*` — `GetUserById`, `GetUserByEmail`, `UpdateProfile`, `DeactivateUser`, `ListUsers` (admin)
- `adapters/outbound/persistence/sqlmodel/models.py` — `UserTable` (no `password_hash`; that lives in `authentication`'s `credentials` table)
- `adapters/outbound/user_registrar/` — `SQLModelUserRegistrarAdapter`: implements authorization's `UserRegistrarPort`
- `adapters/outbound/authz_version/` — `SQLModelUserAuthzVersionAdapter` (and its session-scoped variant): implements `UserAuthzVersionPort`
- Routes: `GET/PATCH/DELETE /me`, `GET /admin/users`

### Authorization feature (`src/features/authorization/`)

Pure ReBAC concerns. Other features call into it through one port; it calls back through three small ports `authentication` and `users` implement.

- `application/ports/authorization_port.py` — `AuthorizationPort` Protocol (`check`, `lookup_resources`, `lookup_subjects`, `write_relationships`, `delete_relationships`)
- `application/registry.py` — `AuthorizationRegistry`: features call `register_resource_type(...)` and `register_parent(...)` at startup; sealed by `main.py` before serving traffic
- `application/use_cases/bootstrap_system_admin.py` — `BootstrapSystemAdmin` (composes `UserRegistrarPort` + `AuthorizationPort` + `AuditPort`)
- `application/ports/outbound/` — `UserAuthzVersionPort` (cache invalidation, implemented by `users`), `UserRegistrarPort` (register-or-lookup for bootstrap, implemented by `users`), `AuditPort` (`authz.*` events, implemented by `authentication`)
- `adapters/outbound/sqlmodel/` — `SQLModelAuthorizationAdapter` (engine-owning) and `SessionSQLModelAuthorizationAdapter` (session-scoped, used by feature UoWs)
- `composition/wiring.py` — `register_authorization_error_handlers(app)` maps `NotAuthorizedError` → 403 and `UnknownActionError` → 500

### Email feature (`src/features/email/`)

- `application/ports/email_port.py` — `EmailPort.send(to, template_name, context) -> Result[None, EmailError]`
- `application/registry.py` — `EmailTemplateRegistry`; features call `register_template(name, path)` at composition; sealed in `main.py`
- `adapters/outbound/console/` — logs the rendered email to stdout (dev/test default)
- `composition/jobs.py` — registers the `send_email` background-jobs handler
- See `docs/email.md`.

### Background-jobs feature (`src/features/background_jobs/`)

- `application/ports/job_queue_port.py` — `JobQueuePort.enqueue(name, payload)` and `enqueue_at(name, payload, run_at)`
- `application/registry.py` — `JobHandlerRegistry`; sealed in `main.py` and `src/worker.py`
- `adapters/outbound/in_process/` — runs handlers inline at enqueue time (dev/test only); the only shipped adapter
- `application/cron.py` — runtime-agnostic `CronSpec` descriptor (relay/prune/auth-purge schedules, declared without a scheduler)
- `src/worker.py` — runtime-agnostic composition-root scaffold (same composition root as `main.py`); `make worker` builds it, logs handlers + cron descriptors, then exits non-zero. No job runtime is wired (the `arq` runtime was removed in ROADMAP ETAPA I step 5; AWS SQS + a Lambda worker arrive at a later roadmap step)
- See `docs/background-jobs.md`.

### File-storage feature (`src/features/file_storage/`)

- `application/ports/file_storage_port.py` — `FileStoragePort.put`/`.get`/`.delete`/`.signed_url`
- `adapters/outbound/local/` — writes to `APP_STORAGE_LOCAL_PATH`, sha256 prefix dirs
- `adapters/outbound/s3/` — real `boto3`-backed `FileStoragePort` adapter, selected with `APP_STORAGE_BACKEND=s3` (requires the `s3` extra and bucket configuration)
- See `docs/file-storage.md`.

### Request flow

```
HTTP → RequestContextMiddleware (X-Request-ID) → ContentSizeLimitMiddleware → FastAPI router
  → require_authorization (resolves principal, calls AuthorizationPort.check)
  → inbound adapter (Pydantic → command/query)
  → use case (domain + outbound ports)
  → Result[contract, ApplicationError]
  → inbound adapter (contract → Pydantic response, or HTTP error)
  → platform error_handlers → application/problem+json
```

### Layer contracts (Import Linter)

Contracts are defined in `pyproject.toml` under `[tool.importlinter]`. Key rules:

- `platform` ↛ `features` (except the configuration composition root, with explicit ignores)
- `domain` ↛ frameworks (FastAPI, SQLModel, Pydantic, Alembic, etc.)
- `application` ↛ adapters, FastAPI, SQLModel, SQLAlchemy, Alembic
- `adapters.inbound` ↛ `adapters.outbound`, no `domain` direct, no SQL libraries
- `adapters.outbound` ↛ `adapters.inbound`, no use cases, no inbound ports
- `authentication` ↛ `authorization` and `authorization` ↛ `authentication`
- `authentication` ↛ `users.adapters`
- `users` ↛ `authentication`
- `users` ↛ `authorization.adapters`
- `email` ↛ other features; `background_jobs` ↛ other features; `file_storage` ↛ other features

Run boundary checks: `make lint-arch`

## Adding a new feature

1. Create `src/features/<name>/` from scratch following the layer stack (`domain → application → adapters → composition`) and the per-feature conventions documented above; add the entity, table, routes, and tests.
2. Decide which resource types your feature owns. For each *leaf* type (one whose tuples will live in the `relationships` table), call `registry.register_resource_type("<type>", actions={...}, hierarchy={...})` from your feature's wiring module. For each *inherited* type (delegates to a parent via a lookup), call `registry.register_parent("<type>", parent_of=..., inherits_from="<parent>")`.
3. Build your feature's container in `main.py` after the authorization container exists; pass `authorization.port` and `authorization.registry` in.
4. Gate your HTTP routes with the platform-level `require_authorization("<action>", "<resource_type>", id_loader=...)` dependency.
5. If the feature needs the authorization tuple write to commit atomically with its own DB writes, take a `user_authz_version_factory` parameter on its container and pass it to the unit-of-work.
6. If the feature sends email, write a template under `src/features/<name>/email_templates/`, register it with `email.registry` at composition, and call `EmailPort.send(...)` (or enqueue the `send_email` background job for non-blocking delivery).
7. If the feature does deferred work, register a handler with `jobs.registry` in both `src/main.py` and `src/worker.py` before sealing.
8. If the feature stores blobs, take a `FileStoragePort` dependency in its container; do not import a specific adapter.
9. No feature should import another feature's modules; cross-feature work goes through application ports.
10. If the feature adds a user-referencing column that holds PII (or anything that should not survive an Art. 17 erasure), update the PII column inventory in `docs/operations.md` AND extend the user-row scrub in `_apply_erasure_scrub` (`src/features/users/adapters/outbound/persistence/sqlmodel/repository.py`). Missing this step is a release-blocking GDPR defect.

## Testing strategy

| Scope | Marker | Location | Notes |
|---|---|---|---|
| Unit | `unit` | `*/tests/unit/` | Pure logic, no IO; uses fakes from `*/tests/fakes/` |
| End-to-end | `e2e` | `*/tests/e2e/` | HTTP flows through FastAPI with in-memory fakes |
| Contract | (called by unit/integration) | `*/tests/contracts/` | Same behavior assertions run against fake and real adapters |
| Integration | `integration` | `*/tests/integration/` | Requires Docker/testcontainers; hits real PostgreSQL |

Coverage gate: `make ci` enforces an 80% line-coverage floor (`pyproject.toml [tool.coverage.report] fail_under`) and a separate 60% branch-coverage floor (`BRANCH_COVERAGE_FLOOR` in the Makefile, override via env).

## Coding conventions

- Use cases return `Result[T, ApplicationError]`, never raise through the application layer. Every feature's base error (`AuthError`, `AuthorizationError`, `EmailError`, `JobError`, `OutboxError`, `FileStorageError`, `UserError`) inherits from `ApplicationError` defined in `src/app_platform/shared/errors.py`. Concrete subclasses MUST be picklable so they round-trip across a serializing job-runtime boundary (the future AWS SQS + Lambda worker; the `arq` runtime was removed in ROADMAP ETAPA I step 5) — if a class requires non-positional constructor arguments, implement `__reduce__` returning `(cls, (positional_args,))` (see `src/app_platform/shared/tests/unit/test_application_error_pickling.py`).
- `@dataclass(slots=True)` for use cases and mutable domain entities; `@dataclass(frozen=True, slots=True)` for immutable commands/queries/contracts.
- FastAPI dependencies are declared as `Annotated` type aliases (see existing `*Dep` names in `adapters/inbound/http/dependencies.py`).
- Feature HTTP errors map application errors to HTTP status codes in `adapters/inbound/http/errors.py`; the platform renders the final Problem Details response.
- New feature code goes under `src/features/<feature_name>/` following the layer stack and the "Adding a new feature" steps above.
- New migrations: update SQLModel tables first, then `uv run alembic revision --autogenerate -m "..."`. **Index changes on tables expected to hold production data MUST use `create_index_concurrently` / `drop_index_concurrently` from `alembic/migration_helpers.py`** — plain `op.create_index` takes `ACCESS EXCLUSIVE` and blocks writes during the build. See `docs/architecture.md` for the rule and the recent `alembic/versions/20260518_0015_users_created_at_index.py` for a worked example.
- Per-feature settings: every feature ships a `composition/settings.py` with a typed projection and a `validate_production(errors: list[str]) -> None` method. `AppSettings` aggregates them.

## Production checklist

The settings validator refuses to start when `APP_ENVIRONMENT=production` and any of these are true:

- `APP_AUTH_JWT_SECRET_KEY` / `APP_AUTH_JWT_ISSUER` / `APP_AUTH_JWT_AUDIENCE` unset
- `APP_CORS_ORIGINS` contains `*`
- `APP_AUTH_COOKIE_SECURE=false`
- `APP_ENABLE_DOCS=true`
- `APP_AUTH_RBAC_ENABLED=false`
- `APP_EMAIL_BACKEND=console` (the only accepted value; production refuses `console` and there is no production email backend yet — AWS SES arrives at a later roadmap step)
- `APP_JOBS_BACKEND=in_process` (the only accepted value; production refuses `in_process` and there is no production job backend yet — the AWS SQS adapter + a Lambda worker arrive at a later roadmap step)
- `APP_AUTH_RETURN_INTERNAL_TOKENS=true`
- `APP_STORAGE_ENABLED=true` with `APP_STORAGE_BACKEND=local`
- `APP_AUTH_REDIS_URL` unset (required for both the auth rate limiter and the principal cache — without it, multi-replica deploys silently multiply rate-limit budgets by worker count and revoked principals keep acting on workers that did not see the in-process cache invalidation)
- `APP_TRUSTED_PROXY_IPS` empty (the auth rate limiter would see the proxy IP for every request behind any load balancer; one attacker exhausts the bucket for the entire user base). Never set to `0.0.0.0/0` — that lets any caller spoof their client IP via `X-Forwarded-For`
- `APP_OUTBOX_ENABLED=false` (request-path consumers write to the outbox unconditionally; the relay must run in production)

See `docs/operations.md` for the full env-var reference.

## Key env vars (auth-related)

| Variable | Default | Purpose |
|---|---|---|
| `APP_AUTH_JWT_SECRET_KEY` | unset | Required in production; signs all JWTs |
| `APP_AUTH_SEED_ON_STARTUP` | `false` | Seeds RBAC roles/permissions on startup |
| `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` | unset | Creates initial super-admin if both are set |
| `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING` | `false` | Default-deny: when `false`, bootstrap refuses to promote an existing account that does not already hold `system:main#admin`. Set to `true` only when intentionally promoting a pre-created account; the supplied password is then verified against the stored credential before any relationship write |
| `APP_AUTH_RETURN_INTERNAL_TOKENS` | `false` | Exposes single-use tokens in responses — test-only; refused in production |
| `APP_AUTH_REDIS_URL` | unset | Enables distributed Redis rate limiter and shared principal cache |
| `APP_AUTH_RATE_LIMIT_ENABLED` | `true` | Enables auth rate limiting |
| `APP_AUTH_RBAC_ENABLED` | `true` | Enables ReBAC checks |
| `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS` | `5` | Bounds the worst-case revocation lag for cached principals |
| `APP_AUTH_TOKEN_RETENTION_DAYS` | `7` | Retention window (days) for the worker's `auth-purge-tokens` cron. Refresh-token rows past `expires_at`/`revoked_at` older than the cutoff and internal-token rows past `used_at`/`expires_at` older than the cutoff are deleted in 10k-row batches |
| `APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES` | `60` | Cadence of the `auth-purge-tokens` cron (snapped to the nearest divisor of 60). Set to `0` to disable the cron entirely (operator kill switch) |

## Key env vars (infrastructure)

| Variable | Default | Purpose |
|---|---|---|
| `APP_EMAIL_BACKEND` | `console` | Only `console` (dev/test); production refuses it and has no email backend until AWS SES at a later roadmap step |
| `APP_JOBS_BACKEND` | `in_process` | Only `in_process` (dev/test); production refuses it and has no job backend until the AWS SQS adapter + a Lambda worker at a later roadmap step |
| `APP_STORAGE_BACKEND` | `local` | `local` for dev/test, `s3` in production when `APP_STORAGE_ENABLED=true` |
| `APP_OUTBOX_ENABLED` | `false` | Must be `true` in production; the worker schedules the relay only when this is set |
| `APP_OUTBOX_RELAY_INTERVAL_SECONDS` | `5.0` | Cron cadence of the relay (snapped to nearest divisor of 60) |
| `APP_OUTBOX_CLAIM_BATCH_SIZE` | `100` | Max rows per claim transaction |
| `APP_OUTBOX_MAX_ATTEMPTS` | `8` | Per-row retry budget before flipping to `failed` |
| `APP_OUTBOX_RETRY_BASE_SECONDS` | `30.0` | Base delay for the relay's exponential retry backoff (`min(base * 2^(attempts-1), max)`) |
| `APP_OUTBOX_RETRY_MAX_SECONDS` | `900.0` | Cap on the retry backoff so a poison row does not stall the queue indefinitely |
