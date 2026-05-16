# Architecture

This document describes how the repository is structured, which features ship
out of the box, and how requests move through the system.

## Overview

The repository uses a feature-first hexagonal architecture. The `platform`
package owns cross-cutting concerns (FastAPI factory, middleware, settings,
error handling, the shared engine, the cross-feature `relationships` table).
The `features` package owns business capabilities. Every feature follows the
same layout — `domain/`, `application/`, `adapters/`, `composition/`, `tests/`
— so adding a new feature means creating that same
`domain/ application/ adapters/ composition/ tests/` layout by hand and
wiring it through the authorization/email/jobs registries.

```text
HTTP client
  -> FastAPI platform app (CORS, trusted hosts, request ID, Problem Details)
  -> Feature inbound HTTP adapter (Pydantic → command/query)
  -> Feature application use case (returns Result[T, ApplicationError])
  -> Feature domain model
  -> Outbound port (e.g. SQLModel repository, EmailPort, JobQueuePort)
  -> Adapter implementation
```

## Feature Inventory

| Feature | Owns | Consumes |
| --- | --- | --- |
| `authentication` | JWT tokens, login/logout/refresh, password reset, email verify, rate limiting, the `credentials` table, principal resolution. | `UserPort` (from `users`), `EmailPort`, `JobQueuePort`, `AuthorizationPort`. |
| `users` | The `User` entity, the `users` table, registration, profile read/update, deactivation, admin user listing. | Authorization's outbound ports (`UserRegistrarPort`, `UserAuthzVersionPort`). |
| `authorization` | `AuthorizationPort`, the runtime `AuthorizationRegistry`, the SQLModel adapter, the SpiceDB stub, `BootstrapSystemAdmin`. | `UserRegistrarPort`, `UserAuthzVersionPort` (implemented by `users`), `AuditPort` (implemented by `authentication`). |
| `email` | `EmailPort`, console + SMTP adapters, the `EmailTemplateRegistry`. | Nothing. |
| `background_jobs` | `JobQueuePort`, in-process + `arq` adapters, the `JobHandlerRegistry`, the worker entrypoint. | Nothing. |
| `file_storage` | `FileStoragePort`, local adapter, S3 stub. | Nothing. |
| `outbox` | `OutboxPort`, the `outbox_messages` table, `SessionSQLModelOutboxAdapter`, the `DispatchPending` relay use case. | `JobQueuePort` (the relay's destination). |

### Dependency Graph

```text
authentication ──▶ users  ──▶ authorization
       │            ▲              │
       │            └──── outbound ports ────┐
       ├──▶ email                            │
       ├──▶ background_jobs                  │
       └──▶ authorization                    │

email, background_jobs, file_storage: have no inbound feature deps.
```

The edges above are runtime calls; Import Linter contracts forbid the
*compile-time* equivalents (e.g. `authentication ↛ authorization` source
imports). Every cross-feature call goes through an application port.

## Main Modules

| Module | Responsibility |
| --- | --- |
| `src/main.py` | Builds the FastAPI app, mounts every feature's routes, and wires the per-feature containers inside the lifespan event. |
| `src/worker.py` | Background-jobs worker entrypoint — loads the same composition root, registers handlers, runs `arq`. |
| `src/app_platform/api/app_factory.py` | Creates the FastAPI app, configures docs URLs, CORS, trusted hosts, request context middleware, content-size limits, and Problem Details handlers. |
| `src/app_platform/config/settings.py` | `AppSettings` — the env-loading boundary. Exposes typed per-feature views via `settings.authentication`, `settings.email`, etc. |
| `src/app_platform/config/sub_settings.py` | `DatabaseSettings`, `ApiSettings`, `ObservabilitySettings` — cross-cutting platform configuration projections. |
| `src/app_platform/persistence/sqlmodel/authorization/` | The cross-feature `relationships` table. Platform-owned because every feature's authz check reads it; the authorization feature is its only writer. |
| `src/app_platform/api/middleware/request_context.py` | Adds or propagates `X-Request-ID` and emits one JSON access log per request. |
| `src/app_platform/api/error_handlers.py` | Converts framework, validation, dependency, application, and unhandled exceptions into `application/problem+json` responses. |
| `alembic/` | Migration environment and versioned schema migrations. |

## Layer Boundaries

Boundaries are enforced by Import Linter contracts in `pyproject.toml`.

| Boundary | Rule |
| --- | --- |
| Platform isolation | `app_platform` must not import `features` (the configuration composition root in `app_platform.config.settings` is the sole tolerated exception, ignored explicitly). |
| Domain purity | Each feature's `domain/` package must not import application, adapters, composition, FastAPI, SQLModel, SQLAlchemy, Alembic, Pydantic, or other framework packages. |
| Application isolation | Each feature's `application/` package must not import adapters, composition, platform API, persistence, FastAPI, SQLModel, SQLAlchemy, Alembic, or other adapter packages. |
| Inbound adapter isolation | Inbound adapters must not bypass application ports to import outbound adapters or domain directly. |
| Outbound adapter isolation | Outbound adapters must not import inbound adapters, use cases, or inbound ports. |
| `authentication ↛ authorization` | Cross-feature dependency goes the other way (authorization defines outbound ports). |
| `authentication ↛ users.adapters` | Authentication uses `UserPort`, not the users adapters directly. |
| `users ↛ authentication` | Users is the upstream owner of the user record; authentication consumes `UserPort`. |
| `users ↛ authorization.adapters` | Users implements authorization's outbound ports but never reaches into its adapter package. |
| `email ↛ other features` | Email is feature-agnostic; features register templates with `EmailTemplateRegistry` instead. |
| `background_jobs ↛ other features` | Same pattern as email: features register handlers, never imported directly. |
| `file_storage ↛ other features` | Same pattern again. |

Run the boundary checks with:

```bash
make lint-arch
```

## Request Data Flow

1. A request enters the FastAPI app created by `build_fastapi_app()`.
2. `RequestContextMiddleware` stores a request ID on `request.state` and writes
   the same ID to the response header.
3. `ContentSizeLimitMiddleware` rejects bodies larger than `APP_MAX_REQUEST_BYTES`.
4. The platform app dispatches to a route under `/auth`, `/me`, `/admin`,
   or a health endpoint.
5. The route's `require_authorization(...)` platform dependency resolves the
   principal from the bearer token (via the authentication feature's
   principal resolver), then asks `AuthorizationPort.check(...)` whether the
   action is allowed.
6. Inbound dependencies resolve the feature's container from `app.state`.
7. The route maps Pydantic request schemas into application commands or queries.
8. The route calls a use case through an inbound `Protocol` type alias.
9. The use case coordinates domain objects and outbound ports.
10. Write use cases use `UnitOfWorkPort`; read use cases use query repository ports.
11. Use cases return `Ok(value)` or `Err(ApplicationError)`.
12. The route maps successful contracts to Pydantic response schemas, or raises
    a feature HTTP exception for application errors.
13. Platform error handlers render Problem Details JSON.

## Cross-feature Communication Patterns

| Concern | Pattern |
| --- | --- |
| Authorization checks | Every feature gates its HTTP routes with the platform `require_authorization(action, resource_type, id_loader=...)` dependency, which calls `AuthorizationPort.check`. |
| Authorization tuples | Resource-creating writes commit the resource row and the `owner` relationship tuple in the same Unit of Work via a session-scoped `AuthorizationPort`. |
| Atomic grant/revoke | `AuthorizationPort.write_relationships` and `.delete_relationships` commit the relationship row and the `authz_version` bump for every affected `user:*` subject inside a single transaction. Callers are responsible for calling `PrincipalCacheInvalidatorPort.invalidate_user(subject_id)` for every affected user after the call returns — the session-scoped path inherits this via UoW commit hooks; the engine path requires explicit invalidation. Cache invalidation is best-effort (any exception is logged at WARNING and swallowed); the durable correctness signal is the in-transaction `authz_version` bump. |
| User lookup from authentication | Authentication takes `UserPort` as a constructor dependency; it never imports `UserTable` or the users repository directly. |
| Sending email | Features call `EmailPort.send(to, template_name, context)`. Authentication's password-reset and email-verify use cases write a `send_email` row to the outbox so the email enqueue commits atomically with the token write. |
| Background work | Features register handlers with `JobHandlerRegistry` and enqueue work through `JobQueuePort`. The web app and the worker share a composition root so the same handler set is visible to both. |
| Atomic side effects | Features that write business state and trigger a side effect in the same use case call `OutboxPort.enqueue` inside the repository's `*_transaction()` context. The relay running in the worker drains pending rows and re-emits them through `JobQueuePort`. See `docs/outbox.md`. |
| File uploads | Features call `FileStoragePort.put` / `.signed_url`; no feature consumes it in the current source tree, but the port is ready to wire. |

## Application Composition

`create_app()` in `src/main.py` separates route mounting from container startup:

- Routes are mounted when the app object is built so OpenAPI generation and
  routing work before lifespan startup completes.
- Per-feature containers are built during lifespan startup. The construction
  order is: `users` → `email` → `background_jobs` → `authentication` →
  `authorization` (which receives `users.user_authz_version_adapter`,
  `users.user_registrar_adapter`, `authentication.audit_adapter`, and a
  `PrincipalCacheInvalidatorAdapter` wrapping `authentication.principal_cache`
  as outbound implementations) → `file_storage`.
- Every container is stored on `app.state` and removed during teardown.
- The shared SQLModel engine is owned by the authentication container today
  (historical; it lives there because it predates the users split) and is
  reused by users. The engine is disposed during shutdown.
- The `AuthorizationRegistry` and `EmailTemplateRegistry` are sealed after
  every feature has had a chance to contribute; subsequent runtime
  registration attempts surface as clear errors.

## Settings Composition

`AppSettings` is the env-loading boundary (pydantic-settings, `APP_` prefix).
Every flat field continues to be the authoritative knob for backwards
compatibility, but the class also constructs typed per-feature views on demand:

```python
settings = get_settings()
settings.email.backend            # EmailSettings projection
settings.authentication.jwt_secret_key
settings.database.dsn
```

The same per-feature classes own their own production-validation methods.
`AppSettings._validate_production_settings` constructs each projection,
calls `validate_production(errors)`, and surfaces every problem as a single
`ValueError`. See `docs/operations.md` for the full env-var reference.

## Error Handling

Feature use cases return application errors rather than raising HTTP exceptions.
Each feature's `adapters/inbound/http/errors.py` maps those application errors
to HTTP status codes and problem-type URIs. The platform handler renders the
final response as `application/problem+json`.

Authorization errors take a slightly different route: `NotAuthorizedError`
raised from `AuthorizationPort.check` is caught by the platform error handler
registered by `register_authorization_error_handlers(app)` and converted to a
403 Problem Details response.

Unhandled exceptions are logged through `api.error` with request ID, method,
path, status code, and error type. The client receives a generic `500`
Problem Details response.

## External Services And Dependencies

| Service | Where | Required when |
| --- | --- | --- |
| PostgreSQL | Every persisting feature | Always. |
| Redis | Auth rate limiter, principal cache, `arq` jobs queue | `APP_AUTH_REDIS_URL` set, multi-replica auth, `APP_JOBS_BACKEND=arq`. |
| SMTP server | Email feature | `APP_EMAIL_BACKEND=smtp` (required in production). |
| Object storage | File-storage feature | A consumer feature wires `FileStoragePort` and `APP_STORAGE_BACKEND=s3` (production). |
| OTLP collector | Observability | `APP_OTEL_EXPORTER_ENDPOINT` set. |
| SpiceDB | Authorization | Not used today; the adapter is a stub mirroring the S3 pattern. |

## Database Migrations

Migrations live under `alembic/versions/`. Each migration declares an
upgrade and downgrade path; `make ci` round-trips them against a real
PostgreSQL container.

**Migrations that touch tables expected to hold production data MUST
use the concurrently helpers for index changes.** PostgreSQL's plain
`CREATE INDEX` / `DROP INDEX` take an `ACCESS EXCLUSIVE` lock on the
target table — fine on a developer laptop, catastrophic on a populated
production table. The helpers in `alembic/migration_helpers.py`
(`create_index_concurrently`, `drop_index_concurrently`) wrap the
statement in `op.get_context().autocommit_block()` so the build runs
without blocking writes:

```python
# ``alembic/`` is on ``sys.path`` via ``prepend_sys_path`` in ``alembic.ini``,
# so the helper is imported as a top-level module rather than as
# ``alembic.migration_helpers`` — the latter would collide with the
# installed ``alembic`` PyPI package.
from migration_helpers import (
    create_index_concurrently,
    drop_index_concurrently,
)

def upgrade() -> None:
    create_index_concurrently(
        "ix_users_created_at",
        "users",
        ["created_at", "id"],
    )

def downgrade() -> None:
    drop_index_concurrently("ix_users_created_at")
```

Both helpers emit `IF [NOT] EXISTS`, so a re-run after a partial failure
is idempotent — important because `CONCURRENTLY` operations can leave
behind invalid index objects when interrupted.

## Design Decisions

| Decision | Reason |
| --- | --- |
| Feature-first hexagonal layout | Keeps business code, adapters, composition, and tests for a feature close together; cross-feature dependencies become deliberate port contracts. |
| Protocol-based ports | Allows tests and adapters to swap implementations without changing use cases. |
| Result type for use cases | Keeps expected business failures explicit without throwing through application logic. |
| Platform-level Problem Details | Gives every error a consistent RFC 9457 shape. |
| Per-feature settings classes | Each feature ships its config and production validation alongside its other code; `AppSettings` aggregates them. |
| Separate credentials table | A `User` can have multiple credentials (password today, passkey tomorrow). Coupling the hash to the user row would force a schema migration when adding new credential types. |
| Background-jobs worker | Email sends are slow; doing them inline turns `POST /auth/password-reset` into a 2 s endpoint. The queue keeps the API responsive and lets the worker absorb retry policy. |
| Email template registry | Templates live with the feature that sends them; the email feature provides the registry rather than owning the templates itself. Mirrors the authorization-registry pattern. |
| S3 and SpiceDB stubs | Both adapters raise `NotImplementedError` from their methods. Real implementations need provider-specific choices (boto3 IAM, SpiceDB hosting) the consumer must make. |

## Tradeoffs And Limitations

- No OAuth/SSO yet — the `credentials` table is shaped to support it, the
  endpoints are not implemented.
- The S3 file-storage adapter is a stub. Filling it in requires `boto3` and
  IAM configuration outside the scope of a starter.
- The SpiceDB authorization adapter is a stub. The SQLModel adapter is the
  default; switching is a one-feature swap when needed.
- No admin web UI; the API surface is the entire admin surface.
- No multi-tenancy primitives (organizations, workspaces). They belong on top
  of `users` in consumer projects.
