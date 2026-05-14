# Operations Guide

This guide describes how to run and operate the service outside a test process.

## Runtime Requirements

- Python 3.14 when running without a container.
- PostgreSQL reachable through `APP_POSTGRESQL_DSN`.
- Applied Alembic migrations.

## Python Install Matrix

After `trim-runtime-deps`, `pyproject.toml` splits runtime dependencies into a
small **core** set plus role / adapter extras. Pick the extras that match the
process you are running and the optional adapters it uses. Local development
keeps a single fat install via the `dev` dependency-group.

| Install command | Brings | Use it for |
| --- | --- | --- |
| `uv sync` | core only (pydantic, sqlmodel, alembic, argon2, OTel, …) | Tooling that just imports the core layers (rare). Does **not** start the API or worker. |
| `uv sync --extra api` | + `fastapi[standard]` (uvicorn, starlette extras, `python-multipart`) | API host |
| `uv sync --extra worker` | + `arq`, `redis` | Background-jobs worker host |
| `uv sync --extra api --extra worker` | + both of the above | Single-host deployments running both roles in one venv |
| `uv sync --extra resend` | + `httpx` | Any host that sets `APP_EMAIL_BACKEND=resend` |
| `uv sync --extra s3` | + `boto3` | Any host that sets `APP_STORAGE_BACKEND=s3` |
| `uv sync` (with the `dev` group) | everything above + test/lint tooling | Local development (`uv sync` reads `[dependency-groups] dev` by default) |

If the API process is configured with `APP_AUTH_REDIS_URL` (distributed rate
limiter or the shared principal cache), install `--extra worker` alongside
`--extra api` — auth imports `redis` lazily but the import must succeed when the
Redis-backed limiter / cache is selected.

If the wrong extra is missing the app fails loudly at startup naming the extra,
for example:

- `APP_EMAIL_BACKEND=resend` without `--extra resend` → `httpx is not installed; the Resend email adapter requires it. Install with: uv sync --extra resend`
- `APP_STORAGE_BACKEND=s3` without `--extra s3` → `boto3 is not installed; the S3 file-storage adapter requires it. Install with: uv sync --extra s3`

> **Backwards-compatibility note.** Deployments that previously ran a bare
> `uv sync` (no extras) and relied on FastAPI being present must now choose at
> least `--extra api` (and `--extra worker` for the worker host). See the
> changelog entry for `trim-runtime-deps`.

## Local Docker Compose

Run the database only:

```bash
docker compose up -d db
```

Run the app and database:

```bash
docker compose up --build
```

Docker Compose builds the Dockerfile `dev` target, runs a one-shot `migrate`
service with `alembic upgrade head`, then starts the app service. The app uses
Uvicorn reload and bind mounts `src/`, `alembic/`, and `alembic.ini`.

Docker Compose sets these environment variables for the app and migrate services:

| Variable | Value |
| --- | --- |
| `APP_ENVIRONMENT` | `development` |
| `APP_ENABLE_DOCS` | `true` |
| `APP_POSTGRESQL_DSN` | `${APP_POSTGRESQL_DSN_DOCKER:-postgresql+psycopg://postgres:postgres@db:5432/kanban}` |

## Container Images

The `Dockerfile` ships **two deployable targets**: one image per process
role. Both stages share a base layer (`runtime`), so deployments get a
clear separation between the API and worker without maintaining two
Dockerfiles.

| Stage | Built with | Runs | Listens on |
| --- | --- | --- | --- |
| `runtime` | `docker build --target runtime …` | `uvicorn main:app --timeout-graceful-shutdown 30` | TCP 8000 |
| `runtime-worker` | `docker build --target runtime-worker …` | `python -m worker` (arq) | none |

The `runtime-worker` stage is declared `FROM runtime AS runtime-worker`,
so it inherits every hardening layer of the API image (digest-pinned
base, UID/GID 10001, tini PID 1, the prebuilt `/app/.venv`) and only
overrides `CMD`. The API HEALTHCHECK is cleared (`HEALTHCHECK NONE`) on
the worker stage because the worker has no HTTP listener — rely on the
orchestrator's exit-code-based liveness check instead.

Build the API image:

```bash
docker build --target runtime -t starter-template-fastapi:prod .
```

Build the worker image (or use `make docker-build-worker`):

```bash
docker build --target runtime-worker -t worker:latest .
```

Run migrations as a separate deployment step (the API image carries
`alembic`; the worker image does too, but the API image is the canonical
release artifact for migrations):

```bash
docker run --rm --env-file .env starter-template-fastapi:prod alembic upgrade head
```

Run the API:

```bash
docker run --env-file .env -p 8000:8000 starter-template-fastapi:prod
```

Run the worker (no port; requires `APP_JOBS_BACKEND=arq` and a reachable
`APP_JOBS_REDIS_URL`):

```bash
docker run --env-file .env worker:latest
```

The API image default command starts Uvicorn and does not run
migrations. The worker image default command starts the arq worker and
does not bind a TCP listener.

### Kubernetes deployment shape

A typical production deployment is one `Deployment` per image, sharing
the same `Secret`/`ConfigMap` for `APP_*` environment variables:

- API `Deployment` runs the `runtime` image with a `livenessProbe` /
  `readinessProbe` against `/health/live` and `/health/ready`.
- Worker `Deployment` runs the `runtime-worker` image with **no HTTP
  probes**; the kubelet restarts the pod on non-zero exit. Set
  `terminationGracePeriodSeconds` ≥ the worker's longest job timeout so
  arq can drain in-flight jobs cleanly on SIGTERM.

Both `Deployment`s SHOULD set `terminationGracePeriodSeconds: 35`
(`APP_SHUTDOWN_TIMEOUT_SECONDS + 5` slack). The inner-process timeout
fires first — uvicorn's `--timeout-graceful-shutdown 30` baked into the
API image and the worker's `on_shutdown` budget — so the kubelet
observes a clean exit instead of a SIGKILL after the grace period
elapses. The 5 s slack covers shell startup, Python interpreter
teardown, and any final OTel/Redis flushes.

Override `APP_SHUTDOWN_TIMEOUT_SECONDS` (default `30.0`) when in-flight
work needs a longer drain window; raise `terminationGracePeriodSeconds`
to match (always `+5` slack).

## Deployment Checklist

- Provision PostgreSQL.
- Set `APP_POSTGRESQL_DSN` to the production DSN.
- Run `alembic upgrade head` as a release step before starting the app.
- Set `APP_ENVIRONMENT=production`.
- Set `APP_TRUSTED_HOSTS` to the public hostnames accepted by the app.
- Set `APP_CORS_ORIGINS` to explicit browser origins if browsers call the API.
- Set `APP_ENABLE_DOCS=false` so Swagger UI, ReDoc, and `/openapi.json` are not exposed.
- Set `APP_WRITE_API_KEY` if write routes should require a shared key.
- Configure liveness checks against `/health/live` and traffic readiness checks
  against `/health/ready`.
- Provision Redis and set `APP_AUTH_REDIS_URL` if the deployment runs more than one replica (see [Rate Limiting](#rate-limiting)).
- Configure observability sinks as needed: `/metrics` for Prometheus and
  `APP_OTEL_EXPORTER_ENDPOINT` for OpenTelemetry traces.

## Dependency Updates (Renovate)

`renovate.json` configures the bot. Two policies worth knowing about:

- **Security PRs are on a fast lane.** `vulnerabilityAlerts` is enabled with
  `prCreation: immediate` and `schedule: ["at any time"]`, so security
  advisories bypass the weekly cadence and `prHourlyLimit`. Patch and minor
  security bumps auto-merge once CI is green; **major-version security bumps
  require human review** (a `packageRules` entry forces `automerge: false` on
  `updateType: "major"`).
- **Routine bumps batch weekly.** The `production-deps`, `dev-deps`, and
  `pre-commit-hooks` groups are scheduled for `before 5am on monday`;
  `lockFileMaintenance` runs `before 9am on monday`.

## Migrations

Apply all migrations:

```bash
uv run alembic upgrade head
```

Rollback one migration:

```bash
uv run alembic downgrade -1
```

Create a new migration after changing SQLModel table definitions:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

Alembic resolves the database URL in this order:

1. `APP_POSTGRESQL_DSN` environment variable.
2. `AppSettings().postgresql_dsn` default or `.env` value.

### Migration Policy

Reversible migrations are the default. Every Alembic migration should ship with an
`upgrade()` and a `downgrade()` that round-trips schema state cleanly.

A migration is **destructive** when its `upgrade()` drops a column, drops a table,
drops an index, or runs raw SQL that does the same (`op.execute("DROP ...")` /
`op.execute("ALTER TABLE ... DROP ...")`). Narrowing an `alter_column` (for
example `String(length=255)` → `String(length=64)`) is also destructive but
cannot be detected statically — the same policy applies, by hand.

Destructive migrations MUST mark `downgrade()` so that the first executable
statement raises `NotImplementedError` with a message that references this
section. For example:

```python
def downgrade() -> None:
    raise NotImplementedError(
        "One-way migration: drop of users.password_hash is not safely "
        "reversible. If you need to revert, restore from backup. "
        "See docs/operations.md#migration-policy."
    )
```

A `downgrade()` that silently re-adds the dropped column with a default value
(or re-creates an empty table) is worse than no downgrade at all — running it
in production would mask data loss. Raising `NotImplementedError` makes the
abort loud and points the operator at this runbook.

**Recovery runbook.** If a destructive migration must be rolled back in
production, the only safe path is to **restore from backup**:

1. Stop the application processes that write to the database.
2. Provision a fresh PostgreSQL instance (or target a recovery instance).
3. Restore the most recent pre-deploy backup using your platform's database
   restore tooling (see [Backups](#backups)).
4. Point `APP_POSTGRESQL_DSN` at the restored instance.
5. Redeploy the application image that matches the restored schema revision.

`uv run alembic downgrade -1` is not an option for destructive revisions — the
`NotImplementedError` will abort the command before any schema change is
applied.

**Escape hatch — `# allow: destructive`.** A destructive `upgrade()` may
suppress the policy on a single line by appending `# allow: destructive` to it:

```python
def upgrade() -> None:
    op.drop_index("ix_legacy_unused")  # allow: destructive
```

Use this only when the downgrade is genuinely reversible — for example, when
dropping an index that can be re-created cheaply, or when removing greenfield
or template-only schema that has never held production data. PR review enforces
the comment; the CI scanner trusts it.

**CI enforcement.** `make migrations-check` runs a pytest scanner over
`alembic/versions/*.py` and fails when a destructive operation is found without
either a raising `downgrade()` or an inline `# allow: destructive` annotation.
`make ci` invokes the scanner alongside the other quality gates.

## Auth And RBAC Bootstrap

Set auth configuration before issuing tokens:

```bash
export APP_AUTH_JWT_SECRET_KEY="set-a-strong-local-secret-outside-git"
```

By default, startup can seed RBAC data and bootstrap the first super admin
automatically when these settings are present:

```bash
export APP_AUTH_SEED_ON_STARTUP=true
export APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL=root@example.com
export APP_AUTH_BOOTSTRAP_SUPER_ADMIN_PASSWORD=root
```

For local Docker Compose, those defaults are already provided unless overridden.
The management commands remain available for manual/one-off operations:

```bash
export AUTH_BOOTSTRAP_PASSWORD="set-a-temporary-password-outside-git"
uv run python -m cli.create_super_admin create-super-admin \
  --email admin@example.com \
  --password-env AUTH_BOOTSTRAP_PASSWORD
unset AUTH_BOOTSTRAP_PASSWORD
```

Public registration never grants administrative permissions. Use the admin RBAC
endpoints only after authenticating as a user with explicit permissions such as
`roles:manage`, `permissions:manage`, or `users:roles:manage`.

### Bootstrapping The First Admin

`BootstrapSystemAdmin` follows a default-deny decision tree so the
configured email cannot silently promote whatever account happens to
own it. The four behavioral paths:

1. **Create-and-grant** — no user exists with the configured email.
   The use case creates the user, writes the `system:main#admin`
   relationship, and emits an `authz.system_admin_bootstrapped`
   audit event with `subevent="created"`.
2. **Idempotent no-op** — a user exists with the configured email
   *and* already holds `system:main#admin`. The use case returns
   `Ok(user_id)` without writing or emitting an audit event. This is
   the safe path for re-running the same deploy.
3. **Refuse-existing** — a user exists with the configured email but
   does NOT yet hold `system:main#admin`, AND
   `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING` is unset or `false`. The
   use case returns `Err(BootstrapRefusedExistingUserError)`; no
   relationship row is written and no audit event is recorded. The
   bootstrap caller (`src/main.py` or `src/cli/create_super_admin.py`)
   logs an ERROR line carrying the offending `user_id` and the
   remediation hint, then exits with `SystemExit(2)` so the deploy
   fails fast rather than starting without an admin.
4. **Promote-existing** — a user exists, is not yet admin, AND
   `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`. The use case verifies
   the supplied bootstrap password against the user's stored
   credential. On a match the relationship is written and an
   `authz.system_admin_bootstrapped` audit event is emitted with
   `subevent="promoted_existing"`. On a mismatch the use case
   returns `Err(BootstrapPasswordMismatchError)`, writes nothing,
   and the caller exits non-zero.

This change closes a privilege-escalation hole: before it landed, a
user who self-registered with the configured admin email was
silently promoted on the next deploy because the supplied bootstrap
password was never checked. Default-deny means that the only
deploys that break on the upgrade are deploys that were silently
exposed to that hole.

The production validator does NOT refuse
`APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`. It is a conscious
opt-in for the legitimate "operator pre-created the account they
intend to promote" workflow; the password-verification step is the
safety check.

### Authorization Cache Window

Authenticated requests resolve the current principal from the access token and
cache it by token ID for up to 30 seconds to avoid a database read on every
request. Role or permission changes are enforced when the cached principal
expires or is explicitly evicted, so emergency authorization revocations can have
a maximum 30-second propagation window per running process.

`POST /auth/logout-all` and password reset revoke refresh tokens and evict cached
principals in the process handling the request. In multi-process or multi-replica
deployments, access-token authorization should still be treated as taking effect
within the documented cache window.

### OAuth Preparation

The service exposes configuration placeholders for a future OAuth provider
integration:

- `APP_AUTH_OAUTH_ENABLED`
- `APP_AUTH_OAUTH_GOOGLE_CLIENT_ID`
- `APP_AUTH_OAUTH_GOOGLE_CLIENT_SECRET`
- `APP_AUTH_OAUTH_GOOGLE_REDIRECT_URI`

OAuth browser/provider flows are not implemented yet; current authentication
is first-party email/password login that returns JWT bearer tokens.

## Rate Limiting

Auth endpoints (login, register, password reset, email verification) are rate-limited
to slow credential-stuffing and abuse. The limiter backend depends on configuration:

| `APP_AUTH_REDIS_URL` | `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT` | Result |
|---|---|---|
| set | any | Redis sliding-window limiter (recommended for all deployments) |
| unset | `false` | In-memory fixed-window limiter (single-replica only) |
| unset | `true` | **Startup failure** — Redis URL is required |

**Multi-replica deployments must use Redis.** Without Redis, each replica applies
the rate limit independently, so the effective limit is `configured_limit × replicas`.

For single-replica deployments, set `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=false`
to acknowledge the in-memory limiter is intentional.

In production with `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=true` (the default)
and no `APP_AUTH_REDIS_URL`, the process will refuse to start.

## Health Checks

The service exposes two distinct probe endpoints:

| Endpoint | Purpose | Returns |
|---|---|---|
| `GET /health/live` | **Liveness** — process is running | 200 always |
| `GET /health/ready` | **Readiness** — all backends reachable | 200 ok / 503 degraded |
| `GET /health` | Alias for `/health/ready` (backward-compatible) | same as above |

### Liveness probe (`/health/live`)

Use this for container restart decisions. No external dependencies are checked.

```bash
curl -s http://localhost:8000/health/live
# {"status":"ok"}
```

### Readiness probe (`/health/ready`)

Use this to gate traffic. Returns HTTP 503 when any backend is unreachable.

```bash
curl -s http://localhost:8000/health/ready
```

Healthy response (HTTP 200):

```json
{
  "status": "ok",
  "persistence": {"backend": "postgresql", "ready": true},
  "auth": {
    "jwt_secret_configured": true,
    "principal_cache_ready": true,
    "rate_limiter_backend": "redis",
    "rate_limiter_ready": true
  }
}
```

Degraded response (HTTP 503):

```json
{
  "status": "degraded",
  "persistence": {"backend": "postgresql", "ready": false}
}
```

### Kubernetes / ECS configuration

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 20
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 15
  failureThreshold: 3
```

## Logs

See [Observability Guide](observability.md) for full metrics, tracing, and log
configuration.

Each request produces an access log from logger `api.request`. Outside
development, logs are emitted as JSON with stable top-level fields:

```json
{
  "timestamp": "2026-05-09T12:00:00.000000+00:00",
  "level": "INFO",
  "logger": "api.request",
  "message": "HTTP request completed",
  "request_id": "abc-123",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "service": {
    "name": "starter-template-fastapi",
    "version": "0.1.0",
    "environment": "production"
  },
  "method": "GET",
  "path": "/api/boards",
  "status_code": 200,
  "duration_ms": 4.21
}
```

Unhandled exceptions are logged through logger `api.error` with request ID,
method, path, status code, and error type.

`APP_LOG_LEVEL` controls the root Python log level. `X-Request-ID` is accepted
from clients when valid and otherwise generated per request.

## Monitoring

Recommended signals:

- `/health/ready` HTTP status and payload fields for backend readiness.
- `/health/live` HTTP status for process liveness.
- Prometheus HTTP RED metrics from `/metrics`.
- OpenTelemetry traces when `APP_OTEL_EXPORTER_ENDPOINT` is set.
- HTTP 5xx count from API responses or ingress logs.
- `api.error` log events.
- Request latency from `duration_ms` in `api.request` logs.
- PostgreSQL connection health and storage metrics.

## Backups

All durable application state is stored in PostgreSQL. Use database-native backup
and restore tooling for the configured PostgreSQL deployment.

No application-level backup job is implemented in this repository.

## Credentials Migration Rollout

The credentials table extraction (`starter-template-foundation` change) ships
as a two-phase migration:

- **Phase 1** (`20260512_0009`) creates the `credentials` table and copies
  every existing `users.password_hash` value into it. The `users.password_hash`
  column is retained, and the login path reads from `credentials` first with
  a documented fallback to `users.password_hash` so deploys can finish without
  locking out in-flight users.
- **Phase 2** (`20260513_0010`) drops `users.password_hash` and removes the
  login fallback. This is the point of no return — after the column is gone
  there is no way to roll back to a phase-0 build without restoring from
  backup.

Deploy phase 2 **only after phase 1 has been live in production for at least
one full release cycle**. The phase-1 backfill copies every active row in a
single transaction, but newly-registered users between phase 0 and phase 1
have no entry to copy; the fallback path covers them on their next login.
Waiting one release cycle gives that fallback time to populate the
`credentials` table for every still-active account.

## Rollback Notes

- Roll back the application image or deployment artifact through your deployment
  platform.
- Review Alembic downgrade functions before rolling back database schema.
- Use `uv run alembic downgrade -1` only when the migration downgrade is safe for
  the data currently stored in PostgreSQL.
- If a migration command fails during deployment, inspect the database migration
  state before retrying.

## Background Jobs

Transactional email and other deferred work are dispatched through the
`background_jobs` feature. The backend is selected at startup via
`APP_JOBS_BACKEND`:

| `APP_JOBS_BACKEND` | Behaviour | Allowed in production |
|---|---|---|
| `in_process` | Runs handlers synchronously inline at enqueue time | **No** — startup fails |
| `arq` | Enqueues onto Redis; a separate worker process consumes the queue | Yes |

In production you **must** run at least one worker process alongside the
API processes; without it, enqueued jobs accumulate in Redis and are
never executed. The worker uses the same composition root as the web
app, so every feature that registers a job handler at startup
(currently just `send_email` from the email feature) sees the same set
of handlers in both processes.

### Configuration

```bash
export APP_JOBS_BACKEND=arq
# Falls back to APP_AUTH_REDIS_URL when this is unset, so single-Redis
# deployments can leave it unset.
export APP_JOBS_REDIS_URL=redis://redis:6379/0
# Optional; defaults to ``arq:queue``.
export APP_JOBS_QUEUE_NAME=arq:queue
```

The settings validator refuses to start in production when:

- `APP_JOBS_BACKEND=in_process`
- `APP_JOBS_BACKEND=arq` and neither `APP_JOBS_REDIS_URL` nor
  `APP_AUTH_REDIS_URL` is set.

### Running the worker

Locally:

```bash
APP_JOBS_BACKEND=arq APP_JOBS_REDIS_URL=redis://localhost:6379/0 \
  make worker
```

In production, run `python -m worker` as a separate process (a
sidecar container, a Kubernetes Deployment, a systemd unit, etc.). The
worker logs the names of every registered job handler at startup so
operators can confirm what it will consume before the first job
arrives.

### Adding a job handler in a feature

1. Write a sync callable `handler(payload: dict[str, Any]) -> None`.
2. In your feature's composition module, expose a
   `register_<name>_handler(registry, ...)` helper that calls
   `registry.register_handler("<name>", handler)`.
3. Call that helper from both `src/main.py` (so the web app can
   enqueue the job) and `src/worker.py` (so the worker can run it)
   before the registry is sealed.

The same handler must be registered in both processes; the
`JobHandlerRegistry` raises `UnknownJobError` if the web app tries to
enqueue a name the worker does not know about.

## Runtime Image Contract

The production `Dockerfile` is hardened for least-privilege execution:

- **Base images are pinned by `@sha256:<digest>`** for both `python:3.12-slim`
  and the `ghcr.io/astral-sh/uv` builder source. Renovate (`renovate.json`
  `packageRules` for `dockerfile`) keeps the digests current.
- **The runtime user is `app` with explicit `UID=10001` and `GID=10001`.**
  Kubernetes manifests deploying this image SHOULD set:

  ```yaml
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
  ```

  Volume mounts that need to be written by the app must be owned by
  `10001:10001` (or use the `fsGroup` so the kubelet `chown`s them).
- **PID 1 is `tini`** (set via `ENTRYPOINT ["tini", "--"]`). It forwards
  SIGTERM/SIGINT to `uvicorn` and reaps zombie children spawned by the
  `HEALTHCHECK` `python -c` probe (and any other subprocesses).
- **`uvicorn` runs with `--timeout-graceful-shutdown 30`**, giving in-flight
  requests up to 30 seconds to drain before the process exits.

## Operational Limitations

- The `runtime` Docker image starts only the API server. Migrations are separate.
- A background worker (`make worker` / `python -m worker`) is required in
  production but is **not** started by the API image; deploy the dedicated
  `runtime-worker` image (`docker build --target runtime-worker …` or
  `make docker-build-worker`) as its own process.
- There is no built-in backup or restore automation.

## Pool sizing

FastAPI dispatches sync route handlers on AnyIO's threadpool. By default
AnyIO runs roughly **40 worker threads** (`min(32, os.cpu_count() + 4)` in
the underlying `ThreadPoolExecutor`, with FastAPI/AnyIO capping at 40).
Every sync handler that opens a SQLAlchemy session holds a connection
out of the pool until it returns, so the pool must be sized to cover the
threadpool's worst-case concurrency or requests will queue on
`QueuePool.checkout()` and the user-visible latency tail will balloon
under load.

The default `DatabaseSettings` therefore ships with `pool_size=20` and
`max_overflow=30` — a total ceiling of **50 connections per replica**,
comfortably above the 40-worker threadpool. The general formula is:

```text
pool_size + max_overflow  >=  threadpool_workers + headroom
```

`headroom` covers background tasks that also check out connections (the
outbox relay tick, scheduled jobs, ad-hoc CLI tools running in the same
process). Five to ten extra slots is usually enough.

Tuning knobs:

| Variable | Default | When to change |
| --- | --- | --- |
| `APP_DB_POOL_SIZE` | `20` | Raise it when you increase the AnyIO threadpool or run on a host with more cores. Each pool slot costs ~10 MiB of Postgres-side memory per replica. |
| `APP_DB_MAX_OVERFLOW` | `30` | Burst capacity for short spikes. Above this, `pool_size + max_overflow` requests get `QueuePool overflow timeout`. |

Operator-side limits to watch:

- **Postgres `max_connections`** must accommodate every replica's
  worst-case ceiling. With the default 50-slot ceiling, 8 replicas alone
  consume 400 connections — leave room for the worker, migrations, and
  ad-hoc psql sessions, or front the database with PgBouncer.
- **PgBouncer transaction pooling** means the template's pool size
  effectively becomes the per-replica *transaction* concurrency budget.
  Sizing the template lower and PgBouncer higher is a common pattern.

## Environment Variable Reference

Every runtime knob is exposed as an `APP_`-prefixed environment variable. The
groupings below mirror the per-feature settings classes in each feature's
`composition/settings.py` (and `src/app_platform/config/sub_settings.py` for the
cross-cutting platform sections). Production-only requirements are noted on
the right; the settings validator refuses to start when any of them are
violated and `APP_ENVIRONMENT=production`.

### Platform — API surface (`ApiSettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `development` | One of `development`, `test`, `production`. |
| `APP_ENABLE_DOCS` | `true` | **Must be `false` in production.** |
| `APP_APP_PUBLIC_URL` | `http://localhost:8000` | Base URL embedded in transactional email links. |
| `APP_APP_DISPLAY_NAME` | `Starter` | Product name used in email subjects/signatures. |
| `APP_CORS_ORIGINS` | `["*"]` | JSON list. **Must not contain `*` in production.** |
| `APP_TRUSTED_HOSTS` | `["*"]` | JSON list of accepted `Host` headers. |
| `APP_MAX_REQUEST_BYTES` | `4194304` | Body-size limit for `ContentSizeLimitMiddleware`. |

### Platform — Database (`DatabaseSettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_POSTGRESQL_DSN` | `postgresql+psycopg://postgres:postgres@localhost:5432/starter` | Connection string. |
| `APP_DB_POOL_SIZE` | `20` | Steady-state pool size. See [Pool sizing](#pool-sizing) for the relationship to AnyIO's threadpool. |
| `APP_DB_MAX_OVERFLOW` | `30` | Burst capacity above pool size. |
| `APP_DB_POOL_RECYCLE_SECONDS` | `1800` | Connection recycle window (defends against idle-cutting load balancers). |
| `APP_DB_POOL_PRE_PING` | `true` | Validate connections before use. |

### Platform — Observability (`ObservabilitySettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_LOG_LEVEL` | `INFO` | Root logging level. |
| `APP_OTEL_EXPORTER_ENDPOINT` | unset | OTLP/HTTP traces endpoint, e.g. `http://localhost:4318/v1/traces`. |
| `APP_OTEL_SERVICE_NAME` | `starter-template-fastapi` | Resource attribute on emitted spans. |
| `APP_OTEL_SERVICE_VERSION` | `0.1.0` | Resource attribute on emitted spans. |
| `APP_METRICS_ENABLED` | `true` | Toggles the Prometheus `/metrics` endpoint. |
| `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS` | `1.0` | Per-dependency timeout for `/health/ready`. |
| `APP_SHUTDOWN_TIMEOUT_SECONDS` | `30.0` | Shared graceful-shutdown budget for the API and the worker. The API image bakes `uvicorn --timeout-graceful-shutdown 30`; the worker's `on_shutdown` waits for the in-flight relay tick up to this budget before disposing the engine and closing Redis. Set the K8s `terminationGracePeriodSeconds` to this value `+ 5 s` slack so the inner-process timeout fires first. |

### Authentication (`AuthenticationSettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_AUTH_JWT_SECRET_KEY` | unset | **Required in production.** Signs all access tokens. |
| `APP_AUTH_JWT_ALGORITHM` | `HS256` | One of `HS256`, `RS256`. |
| `APP_AUTH_JWT_ISSUER` | unset | **Required in production.** |
| `APP_AUTH_JWT_AUDIENCE` | unset | **Required in production.** |
| `APP_AUTH_JWT_LEEWAY_SECONDS` | `10` | Clock-skew tolerance (`0`–`60`). |
| `APP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT lifetime. |
| `APP_AUTH_REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh-cookie lifetime. |
| `APP_AUTH_COOKIE_SECURE` | `false` | **Must be `true` in production.** |
| `APP_AUTH_COOKIE_SAMESITE` | `strict` | One of `lax`, `strict`, `none`. |
| `APP_AUTH_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | `30` | TTL for password-reset tokens. |
| `APP_AUTH_EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES` | `1440` | TTL for verify-email tokens. |
| `APP_AUTH_RATE_LIMIT_ENABLED` | `true` | Toggles auth-route rate limiting. |
| `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT` | `false` | Forces Redis-backed rate limiter; **requires `APP_AUTH_REDIS_URL` in production**. |
| `APP_AUTH_REDIS_URL` | unset | Enables distributed rate limiter and principal cache. |
| `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS` | `5` | Bounds revocation lag for the principal cache. |
| `APP_AUTH_REQUIRE_EMAIL_VERIFICATION` | `false` | Block login until email is verified. |
| `APP_AUTH_SEED_ON_STARTUP` | `false` | Bootstrap RBAC and (optionally) a super admin. |
| `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL` | unset | Together with `..._PASSWORD`, seeds the first admin. |
| `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_PASSWORD` | unset | Set with `..._EMAIL` to bootstrap. |
| `APP_AUTH_DEFAULT_USER_ROLE` | `user` | Role assigned on registration. |
| `APP_AUTH_SUPER_ADMIN_ROLE` | `super_admin` | Marker role for system-admin bootstrap. |
| `APP_AUTH_OAUTH_ENABLED` | `false` | Reserved for future OAuth wiring. |
| `APP_AUTH_OAUTH_GOOGLE_CLIENT_ID` | unset | Reserved for future OAuth wiring. |
| `APP_AUTH_OAUTH_GOOGLE_CLIENT_SECRET` | unset | Reserved for future OAuth wiring. |
| `APP_AUTH_OAUTH_GOOGLE_REDIRECT_URI` | unset | Reserved for future OAuth wiring. |
| `APP_AUTH_RETURN_INTERNAL_TOKENS` | `false` | Exposes single-use reset/verify tokens in API responses. **Must be `false` in production.** |

### Authorization (`AuthorizationSettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_AUTH_RBAC_ENABLED` | `true` | **Must stay `true` in production.** Disabling skips authorization checks. |
| `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS` | `5` | Shared with authentication — see above. |

### Users (`UsersSettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_AUTH_DEFAULT_USER_ROLE` | `user` | Shared with authentication — see above. |
| `APP_AUTH_SUPER_ADMIN_ROLE` | `super_admin` | Shared with authentication — see above. |
| `APP_AUTH_REQUIRE_EMAIL_VERIFICATION` | `false` | Shared with authentication — see above. |

### Email (`EmailSettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_EMAIL_BACKEND` | `console` | One of `console`, `smtp`, `resend`. **Must be `smtp` or `resend` in production.** |
| `APP_EMAIL_FROM` | unset | Required when `APP_EMAIL_BACKEND` is `smtp` or `resend`. |
| `APP_EMAIL_SMTP_HOST` | unset | Required when `APP_EMAIL_BACKEND=smtp`. |
| `APP_EMAIL_SMTP_PORT` | `587` | Submission port. |
| `APP_EMAIL_SMTP_USERNAME` | unset | Optional SMTP auth username. |
| `APP_EMAIL_SMTP_PASSWORD` | unset | Optional SMTP auth password. |
| `APP_EMAIL_SMTP_USE_STARTTLS` | `true` | STARTTLS upgrade on the submission port. |
| `APP_EMAIL_SMTP_USE_SSL` | `false` | Implicit TLS (port 465). Mutually exclusive with STARTTLS. |
| `APP_EMAIL_SMTP_TIMEOUT_SECONDS` | `10.0` | Socket timeout for SMTP operations. |
| `APP_EMAIL_RESEND_API_KEY` | unset | Required when `APP_EMAIL_BACKEND=resend`. |
| `APP_EMAIL_RESEND_BASE_URL` | `https://api.resend.com` | Resend API base URL. Use `https://api.eu.resend.com` for the EU data plane. |

### Background jobs (`JobsSettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_JOBS_BACKEND` | `in_process` | One of `in_process`, `arq`. **Must be `arq` in production.** |
| `APP_JOBS_REDIS_URL` | unset | Required when `APP_JOBS_BACKEND=arq`; falls back to `APP_AUTH_REDIS_URL`. |
| `APP_JOBS_QUEUE_NAME` | `arq:queue` | `arq` queue name. |
| `APP_JOBS_KEEP_RESULT_SECONDS_DEFAULT` | `300` | TTL for `arq:queue:result:*` keys when a handler does not override `keep_result_seconds`. Bounds Redis memory. See `docs/background-jobs.md#redis-operational-guidance`. |
| `APP_JOBS_MAX_JOBS` | `16` | Max concurrent jobs per arq worker. Tune to deployment CPU/memory. |
| `APP_JOBS_JOB_TIMEOUT_SECONDS` | `600` | Hard kill for a single job. A handler that overruns is terminated rather than pinning a worker. |

### Transactional outbox (`OutboxSettings`)

The outbox routes request-path side effects through `outbox_messages`
so they commit atomically with the surrounding business write. See
`docs/outbox.md` for the full pattern.

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_OUTBOX_ENABLED` | `false` | Master switch. **Must be `true` in production** (use cases write to the outbox unconditionally; the relay must run to drain them). |
| `APP_OUTBOX_RELAY_INTERVAL_SECONDS` | `5.0` | Relay cron cadence (snapped to nearest divisor of 60). |
| `APP_OUTBOX_CLAIM_BATCH_SIZE` | `100` | Max rows per claim transaction. |
| `APP_OUTBOX_MAX_ATTEMPTS` | `8` | Per-row retry budget before a row flips to `failed`. |
| `APP_OUTBOX_WORKER_ID` | `<hostname>:<pid>` | Stamped onto `locked_by` for operator visibility. |
| `APP_OUTBOX_RETRY_BASE_SECONDS` | `30.0` | Base delay for the relay's exponential retry backoff (`min(base * 2^(attempts-1), max)`). |
| `APP_OUTBOX_RETRY_MAX_SECONDS` | `900.0` | Cap on the retry backoff so a poison row does not stall the queue indefinitely. |
| `APP_OUTBOX_RETENTION_DELIVERED_DAYS` | `7` | Delivered rows older than this are pruned by the hourly worker cron. |
| `APP_OUTBOX_RETENTION_FAILED_DAYS` | `30` | Failed rows older than this are pruned by the hourly worker cron. Operator-actionable evidence is kept longer than delivered audit trail. |
| `APP_OUTBOX_PRUNE_BATCH_SIZE` | `1000` | Max rows the prune cron deletes per transaction; the use case loops until the eligible set is empty. |

### File storage (`StorageSettings`)

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_STORAGE_ENABLED` | `false` | Set `true` when a consumer feature wires `FileStoragePort`. |
| `APP_STORAGE_BACKEND` | `local` | One of `local`, `s3`. **Must be `s3` in production when `APP_STORAGE_ENABLED=true`.** |
| `APP_STORAGE_LOCAL_PATH` | unset | Required when `APP_STORAGE_BACKEND=local`. |
| `APP_STORAGE_S3_BUCKET` | unset | Required when `APP_STORAGE_BACKEND=s3`. |
| `APP_STORAGE_S3_REGION` | `us-east-1` | AWS region for the bucket. |

## GDPR / data subject rights

The platform supports both **right to erasure** (Art. 17) and **right of
access** (Art. 15) via dedicated routes; the implementation scrubs PII
in-place rather than hard-deleting rows so audit-trail row counts and
foreign-key integrity survive.

### Erasure routes

| Route | Trigger | Re-auth | Response |
| --- | --- | --- | --- |
| `DELETE /me/erase` | Self-service (GDPR Art. 17) | Current password in body | `202 Accepted` with `{status, job_id, estimated_completion_seconds}` |
| `POST /admin/users/{user_id}/erase` | Operator-driven | `manage_users` on `system:main` | Same 202 contract |

Both routes enqueue an `erase_user` background job — the actual scrub
runs in the worker process, and the HTTP response returns immediately
with a `Location: /…/erase/status/<job_id>` header. The status
endpoint itself is intentionally out of scope; clients accept
"no body, you'll get notified" semantics.

The self-service route requires the user's **current password** in
the request body so a stolen access token cannot erase the account on
its own. Users without a password credential (future SSO-only flows)
currently get a 401 from the verifier; a follow-up change can add a
"fresh access token issued < 5 min ago" branch without altering the
response shape.

### Export route

| Route | Trigger | Response |
| --- | --- | --- |
| `GET /me/export` | Self-service (GDPR Art. 15) | `200 OK` with `{download_url, expires_at}` |
| `GET /admin/users/{user_id}/export` | Operator-driven, `manage_users` on `system:main` | Same shape |

The use case serialises the user row, profile fields, audit events,
and file-storage metadata to a JSON blob written via
`FileStoragePort.put(...)` and returns a 15-minute signed URL. The
backend determines the URL shape: S3 issues a presigned GET; the local
adapter returns a `file://` URI; tests return `memory://<key>`.

### PII column inventory

The erasure scrub MUST clear every column listed below; new
user-referencing columns extend this table. See the rule in
`CLAUDE.md` "Adding a new feature" — adding a PII-bearing column
without updating the scrub or this table is a release-blocking
defect.

| Table | Column / key | Erasure action |
| --- | --- | --- |
| `users` | `email` | Replaced with `erased+<user_id>@erased.invalid` |
| `users` | `last_login_at` | Set to `NULL` |
| `users` | `is_active` | Set to `false` |
| `users` | `is_erased` | Set to `true` (the authoritative signal) |
| `users` | `authz_version` | Bumped (cached principals dissolve in TTL) |
| `users` | `is_verified` | Preserved (a non-PII state fact) |
| `auth_audit_events` | `ip_address` | Nulled |
| `auth_audit_events` | `user_agent` | Nulled |
| `auth_audit_events` | `event_metadata.family_id` | Key removed from JSONB |
| `auth_audit_events` | `event_metadata.ip_address` | Key removed from JSONB |
| `auth_audit_events` | `event_metadata.user_agent` | Key removed from JSONB |
| `credentials` | (entire row) | Deleted |
| `refresh_tokens` | (entire row) | Deleted |
| `auth_internal_tokens` | (entire row) | Deleted |
| `file_storage` | every blob under `users/{user_id}/` | Deleted via the `delete_user_assets` background job |

### Runbook: handling a written request from legal

1. Confirm the request identifies a single user by email or user id.
2. Look up the user id with `SELECT id, is_active, is_erased FROM users
   WHERE email = ...;` — if `is_erased=true` the work is already done.
3. Invoke `POST /admin/users/{user_id}/erase` from an operator session
   that holds `manage_users` on `system:main`.
4. Confirm `is_erased=true` and that no rows remain in `credentials`,
   `refresh_tokens`, `auth_internal_tokens` for the user.
5. Confirm the `delete_user_assets` outbox row reached `delivered`
   (check `SELECT status FROM outbox_messages WHERE job_name =
   'delete_user_assets' AND payload->>'user_id' = '<user_id>';`). If
   it stayed `pending` past one retry cycle, see the
   [outbox runbook](outbox.md#failed-rows).
6. If legal requires *hard delete* with no row stub, follow up with a
   direct `DELETE FROM users WHERE id = '<user_id>'` — the
   `is_erased` row's column values are scrubbed, so a follow-up
   delete is safe (no PII to leak) and FK cascades remove dependent
   rows.

### Non-goals

- **Third-party data erasure.** Operators must kick off downstream
  erasure (analytics, mail-provider, SaaS integrations) out-of-band.
- **Regulator-grade audit logging.** The `user.erased` event lives in
  the existing `auth_audit_events` table; promote to a tamper-evident
  store if compliance requires it.
- **Status / progress endpoint.** The 202 response carries a
  `Location` header; the status endpoint itself is out of scope for
  the current change.
