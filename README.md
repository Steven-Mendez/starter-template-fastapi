# starter-template-fastapi

`starter-template-fastapi` is a production-shaped starter for FastAPI
services. It bundles the four pieces of infrastructure every real backend
needs — authentication, users, authorization, transactional email — plus
ports for background jobs and file storage, all sitting on a feature-first
hexagonal layout enforced by Import Linter.

The intended first move on a new project is **clone, run, then build your
first feature from scratch** following the documented hexagonal layout
(`domain/ application/ adapters/ composition/ tests/`) so the routes,
persistence, and authorization wiring follow the same conventions as the
bundled features.

## What's New

The `starter-template-foundation` change reshaped the repository: the
`auth` feature split into `authentication` + `users`, and three
infrastructure features (`email`, `background_jobs`, `file_storage`) were
added. See
[`openspec/changes/starter-template-foundation/`](openspec/changes/starter-template-foundation/)
for the full proposal.

## Documentation

- [Architecture](docs/architecture.md) — module boundaries, the feature
  inventory, and the dependency graph.
- [API Reference](docs/api.md) — routes, schemas, authentication, status
  codes.
- [Developer Guide](docs/development.md) — local workflow, testing,
  conventions.
- [Operations Guide](docs/operations.md) — deployment, migrations,
  health checks, **the env-var reference table**, rollback notes.
- [Observability Guide](docs/observability.md) — Prometheus, OTel
  tracing, structured logs.
- [Email](docs/email.md) — `EmailPort`, the `console` adapter,
  templates.
- [Background Jobs](docs/background-jobs.md) — `JobQueuePort`, the
  in-process adapter, the worker scaffold (the production job runtime
  arrives at a later roadmap step).
- [File Storage](docs/file-storage.md) — `FileStoragePort`, local/S3
  adapters.

## Feature Inventory

| Feature | Role |
| --- | --- |
| `authentication` | JWT issuance, login/logout, refresh, password reset, email verify, rate limiting, principal resolution, credential storage. |
| `users` | The `User` entity, registration, profile read/update, deactivation, admin user listing. Owns the `UserPort` consumed by `authentication`. |
| `authorization` | ReBAC engine. Owns `AuthorizationPort`, the runtime registry, and the SQLModel adapter. |
| `email` | `EmailPort` plus the `console` adapter (dev/test; production email arrives with AWS SES at a later roadmap step). Owns the template registry features contribute to. |
| `background_jobs` | `JobQueuePort` plus the `in_process` adapter (dev/test; the production job runtime, AWS SQS + a Lambda worker, arrives at a later roadmap step). Worker scaffold at `python -m worker`. |
| `file_storage` | `FileStoragePort` plus `local` adapter and `s3` stub. |

Cross-feature communication goes through ports only; Import Linter
contracts forbid direct imports (e.g. `authentication ↛ authorization`,
`users ↛ authentication`, `file_storage ↛ other features`).

## Tech Stack

| Area | Tooling |
| --- | --- |
| Runtime | Python 3.14, FastAPI, Uvicorn |
| Data validation | Pydantic 2, pydantic-settings |
| Persistence | PostgreSQL, SQLModel, SQLAlchemy, psycopg |
| Migrations | Alembic |
| Background jobs | in-process adapter (the production job runtime, AWS SQS + a Lambda worker, arrives at a later roadmap step) |
| Dependency management | uv |
| Testing | pytest, pytest-cov, pytest-html, testcontainers |
| Quality gates | Ruff, mypy, Import Linter, pre-commit |
| Containers | Docker, Docker Compose |
| Observability | Prometheus metrics, OpenTelemetry tracing, JSON logs |

## Project Structure

```text
.
├── alembic/                            # Alembic environment and migrations
├── docs/                               # Project documentation
├── openspec/                           # Active and archived change proposals
├── src/
│   ├── main.py                         # API composition entrypoint
│   ├── worker.py                       # Background-jobs worker entrypoint
│   ├── platform/                       # Feature-agnostic platform code
│   │   ├── api/                        # App factory, middleware, error handlers
│   │   ├── config/                     # AppSettings + per-feature sub-settings
│   │   ├── persistence/                # Shared engine + relationships table
│   │   └── shared/                     # Result helper, cross-feature ports
│   └── features/
│       ├── authentication/             # Tokens, login, refresh, password reset, credentials
│       ├── users/                      # User entity + lifecycle, UserPort
│       ├── authorization/              # ReBAC engine, AuthorizationPort, registry
│       ├── email/                      # EmailPort, console adapter, templates
│       ├── background_jobs/            # JobQueuePort, in-process adapter, worker scaffold
│       └── file_storage/               # FileStoragePort, local/S3 adapters
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── uv.lock
```

## Quick Start

Prerequisites:

- Python 3.14.
- `uv` for dependency management.
- Docker if you want the bundled PostgreSQL/Redis or integration tests.

Start the API with a local PostgreSQL container:

```bash
cp .env.example .env
uv sync
docker compose up -d db
uv run alembic upgrade head
make dev
```

Then open:

- `http://localhost:8000/health/live` for liveness.
- `http://localhost:8000/health/ready` for readiness.
- `http://localhost:8000/metrics` for Prometheus metrics.
- `http://localhost:8000/docs` for Swagger UI when `APP_ENABLE_DOCS=true`.

Register a user against the bundled `authentication` feature:

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"a-secure-password"}'
```

## Starting A New Project

1. Clone this repository and rename the remote/origin to your project.
2. Create `src/features/<your-feature>/` with the
   `domain/ application/ adapters/ composition/ tests/` layout.
3. Add the entity, the table, the routes, and the tests — follow the
   "Adding a new feature" steps in
   [`CLAUDE.md`](CLAUDE.md#adding-a-new-feature).
4. Register the new feature with the authorization registry in
   `src/main.py` (one `registry.register_resource_type(...)` call).
5. Generate an Alembic revision for your new table:
   `uv run alembic revision --autogenerate -m "add <your-feature>"`.

You now have authentication, users, authorization, email, background
jobs, and file storage wired in — your first PR should be your domain
code, not the infrastructure it sits on.

## Installation

Install dependencies from `pyproject.toml` and `uv.lock`:

```bash
uv sync
```

Install Git hooks if you want local pre-commit and pre-push checks:

```bash
make precommit-install
```

## Environment Variables

Settings use the `APP_` prefix and are loaded from `.env` by
`app_platform.config.settings.AppSettings`. Every flat field is also
exposed through a typed per-feature view (`settings.authentication`,
`settings.email`, …) so consumers can ask for the structured shape.

See the **[Environment Variable Reference](docs/operations.md#environment-variable-reference)**
in `docs/operations.md` for the full, per-feature table including
defaults, allowed values, and the production-only constraints. The most
common ones to know up front:

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `development` | One of `development`, `test`, `production`. |
| `APP_POSTGRESQL_DSN` | `postgresql+psycopg://postgres:postgres@localhost:5432/starter` | Database DSN. |
| `APP_AUTH_JWT_SECRET_KEY` | unset | **Required in production.** |
| `APP_AUTH_REDIS_URL` | unset | Redis URL for distributed rate limiting and the principal cache. |
| `APP_EMAIL_BACKEND` | `console` | Only `console` (dev/test); production email not yet available (AWS SES at a later roadmap step). |
| `APP_JOBS_BACKEND` | `in_process` | Only `in_process` (dev/test); production refuses it — the production job runtime (AWS SQS + a Lambda worker) arrives at a later roadmap step. |

## Running Locally

Run with auto-reload on the host:

```bash
make dev
```

Run a production-style Uvicorn server locally after applying migrations:

```bash
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Build the worker scaffold (no job runtime is wired — it logs the
registered handlers/cron descriptors and exits non-zero; the AWS SQS +
Lambda worker arrives at a later roadmap step):

```bash
make worker
```

Run the app and database through Docker Compose:

```bash
docker compose up --build
```

## Running Tests

Run unit and end-to-end tests that do not require Docker:

```bash
make test
```

Run integration tests that use Docker and testcontainers:

```bash
make test-integration
```

Run the full local CI gate:

```bash
make ci
```

Generate a coverage report:

```bash
make cov-html
```

`make ci` enforces a **line-coverage floor of 80%** and a separate
**branch-coverage floor of 60%** (the latter via `BRANCH_COVERAGE_FLOOR` in
the Makefile). See [Quality Gates](docs/development.md#quality-gates) for the
full breakdown.

## Building For Production

Build the runtime image:

```bash
docker build --target runtime -t starter-template-fastapi:prod .
```

Run migrations as a separate deployment step with a PostgreSQL DSN reachable from
the container:

```bash
docker run --rm --env-file .env starter-template-fastapi:prod alembic upgrade head
```

Run the service:

```bash
docker run --env-file .env -p 8000:8000 starter-template-fastapi:prod
```

Run the worker alongside it:

```bash
docker run --env-file .env starter-template-fastapi:prod python -m worker
```

The runtime image default command starts Uvicorn and does not run
migrations or the worker.

## Deployment Notes

- Provision PostgreSQL and Redis before starting the app.
- Set `APP_POSTGRESQL_DSN` and `APP_AUTH_REDIS_URL`.
- Run `alembic upgrade head` before starting the production app container.
- Set `APP_ENVIRONMENT=production` — the settings validator refuses to start
  with `console` email, `in_process` jobs, `*` CORS, insecure cookies,
  `auth_return_internal_tokens`, or RBAC disabled. See
  [Operations Guide](docs/operations.md#environment-variable-reference) for the
  full list.
- Run at least one worker (`python -m worker`) per Redis-backed deployment;
  the API does not consume the job queue itself.
- Use `/health/live` for liveness and `/health/ready` for readiness checks.

## Common Commands

| Command | Purpose |
| --- | --- |
| `make sync` | Install dependencies with `uv sync`. |
| `make dev` | Run the API with FastAPI auto-reload. |
| `make worker` | Run the background-jobs worker. |
| `make format` | Format code with Ruff. |
| `make lint` | Run Ruff lint checks. |
| `make lint-arch` | Run Import Linter architecture contracts. |
| `make typecheck` | Run mypy. |
| `make quality` | Run lint, architecture lint, and type checks. |
| `make test` | Run non-integration tests. |
| `make test-integration` | Run Docker-backed integration tests. |
| `make test-e2e` | Run end-to-end HTTP tests. |
| `make test-feature FEATURE=authentication` | Run tests for one feature. |
| `make cov` | Run tests with terminal coverage (gates line 80% + branch 60%). |
| `make report` | Generate HTML test and coverage reports under `reports/`. |
| `make clean-reports` | Remove generated report artifacts. |
| `make ci` | Run the full local gate. |

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `make dev` cannot connect to PostgreSQL | Start `docker compose up -d db` or set `APP_POSTGRESQL_DSN` to a reachable database. |
| `docker compose up --build` exits before the app starts | Check the `migrate` service logs; the app waits for migrations to complete. |
| `uv run alembic upgrade head` uses the wrong database | Check `APP_POSTGRESQL_DSN`; Alembic reads it before the default in `AppSettings`. |
| Auth requests return `401` after working before | The principal cache evicted; the access token may have been revoked or expired. |
| `/health/ready` returns `503` | A readiness dependency failed. Check database, Redis, and auth configuration. |
| Background jobs accumulate without running | The worker process is not running; start `python -m worker`. |
| Integration tests are skipped | Docker is unavailable or `KANBAN_SKIP_TESTCONTAINERS=1` is set. |
| Architecture lint fails | Check imports against the layer contracts in `pyproject.toml`. |

## Contribution Notes

There is no separate `CONTRIBUTING.md`. Follow these rules for changes:

- Keep platform code independent from feature packages.
- Keep domain code free of FastAPI, Pydantic, SQLModel, SQLAlchemy, Alembic, and
  other adapter concerns.
- Keep application code free of FastAPI, SQLModel, SQLAlchemy, Alembic, and
  adapter concerns.
- Cross-feature work goes through ports — Import Linter forbids direct imports.
- Add new feature code under `src/features/<feature_name>/` and put its tests
  next to it under `src/features/<feature_name>/tests/`.
- Run `make quality` and `make test` before opening a pull request.
- Run `make test-integration` when persistence behavior changes.
