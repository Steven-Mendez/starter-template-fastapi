# Operations Guide

This guide describes how to run and operate the service outside a test process.

## Runtime Requirements

- Python 3.14 when running without a container.
- PostgreSQL reachable through `APP_POSTGRESQL_DSN`.
- Applied Alembic migrations.

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

## Container Image

Build the runtime image:

```bash
docker build --target runtime -t starter-template-fastapi:prod .
```

Run migrations as a separate deployment step:

```bash
docker run --rm --env-file .env starter-template-fastapi:prod alembic upgrade head
```

Run the app:

```bash
docker run --env-file .env -p 8000:8000 starter-template-fastapi:prod
```

The runtime image default command starts Uvicorn and does not run migrations.

## Deployment Checklist

- Provision PostgreSQL.
- Set `APP_POSTGRESQL_DSN` to the production DSN.
- Run `alembic upgrade head` as a release step before starting the app.
- Set `APP_ENVIRONMENT=production`.
- Set `APP_TRUSTED_HOSTS` to the public hostnames accepted by the app.
- Set `APP_CORS_ORIGINS` to explicit browser origins if browsers call the API.
- Set `APP_ENABLE_DOCS=false` so Swagger UI, ReDoc, and `/openapi.json` are not exposed.
- Set `APP_WRITE_API_KEY` if write routes should require a shared key.
- Configure the load balancer or orchestrator to check `/health`.

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
uv run python -m src.features.auth.management seed
export AUTH_BOOTSTRAP_PASSWORD="set-a-temporary-password-outside-git"
uv run python -m src.features.auth.management create-super-admin \
  --email admin@example.com \
  --password-env AUTH_BOOTSTRAP_PASSWORD
unset AUTH_BOOTSTRAP_PASSWORD
```

Public registration never grants administrative permissions. Use the admin RBAC
endpoints only after authenticating as a user with explicit permissions such as
`roles:manage`, `permissions:manage`, or `users:roles:manage`.

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

## Health Checks

Use:

```bash
curl -s http://localhost:8000/health
```

Healthy response:

```json
{
  "status": "ok",
  "persistence": {
    "backend": "postgresql",
    "ready": true
  }
}
```

Degraded response:

```json
{
  "status": "degraded",
  "persistence": {
    "backend": "postgresql",
    "ready": false
  }
}
```

The endpoint returns HTTP `200` in both cases. Alerting should inspect
`persistence.ready` or `status`, not only the HTTP status code.

## Logs

Each request produces a JSON access log from logger `api.request`:

```json
{
  "request_id": "abc-123",
  "method": "GET",
  "path": "/api/boards",
  "status_code": 200,
  "duration_ms": 4.21
}
```

Unhandled exceptions are logged through logger `api.error` with request ID,
method, path, status code, and error type.

The `APP_LOG_LEVEL` setting exists but is not applied to logging configuration by
the current code. Configure logging in the process manager, container runtime, or
Python logging setup used to launch the service.

## Monitoring

Recommended signals:

- `/health` payload field `persistence.ready`.
- HTTP 5xx count from API responses or ingress logs.
- `api.error` log events.
- Request latency from `duration_ms` in `api.request` logs.
- PostgreSQL connection health and storage metrics.

No metrics endpoint is implemented in the current source code.

## Backups

All durable application state is stored in PostgreSQL. Use database-native backup
and restore tooling for the configured PostgreSQL deployment.

No application-level backup job is implemented in this repository.

## Rollback Notes

- Roll back the application image or deployment artifact through your deployment
  platform.
- Review Alembic downgrade functions before rolling back database schema.
- Use `uv run alembic downgrade -1` only when the migration downgrade is safe for
  the data currently stored in PostgreSQL.
- If a migration command fails during deployment, inspect the database migration
  state before retrying.

## Operational Limitations

- The runtime Docker image starts only the API server. Migrations are separate.
- There is no built-in metrics endpoint.
- There is no built-in background worker.
- There is no built-in backup or restore automation.
- Readiness degradation is reported in the response body, not the HTTP status.
