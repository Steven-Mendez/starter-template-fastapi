# starter-template-fastapi

`starter-template-fastapi` is a FastAPI service that exposes a Kanban board API.
It is intended for developers who want a working example of a feature-first,
hexagonal FastAPI application with PostgreSQL persistence, Alembic migrations,
API-key-protected write routes, Problem Details error responses, and layered test
coverage.

The current implementation contains one active feature, `kanban`. The
`src/features/_template` package is an inert scaffold for adding more features.

## Documentation

- [Architecture](docs/architecture.md) explains the high-level design, module
  boundaries, data flow, and tradeoffs.
- [API Reference](docs/api.md) documents routes, schemas, authentication, status
  codes, and examples.
- [Developer Guide](docs/development.md) explains local workflow, testing,
  debugging, conventions, and where to add code.
- [User Guide](docs/user-guide.md) shows how to use the Kanban API workflows.
- [Operations Guide](docs/operations.md) covers deployment, migrations, logs,
  health checks, backups, and rollback notes.
- [Observability Guide](docs/observability.md) covers Prometheus metrics,
  OpenTelemetry tracing, and structured logs.
- [Feature Template Guide](docs/feature-template.md) explains how to copy and
  adapt `src/features/_template`.

## What It Does

The service manages Kanban boards, columns, and cards over HTTP. Clients can
create boards, add columns to boards, create cards inside columns, move cards,
patch card metadata, delete columns, and delete boards.

## Who It Is For

- Backend developers building or studying FastAPI services.
- Teams that want a feature-first layout with explicit domain, application,
  adapter, and composition boundaries.
- Developers who need a small but complete API service with PostgreSQL,
  migrations, tests, Docker, and CI wiring.

## Core Features

- FastAPI application factory with request ID middleware and structured logs.
- Kanban board, column, and card HTTP API under `/api`.
- Liveness/readiness endpoints at `/health/live`, `/health/ready`, and `/health`.
- Prometheus metrics at `/metrics` and opt-in OpenTelemetry tracing.
- Optional single API key requirement for write endpoints.
- RFC 9457-style `application/problem+json` error responses.
- SQLModel persistence backed by PostgreSQL.
- Alembic migrations for the database schema.
- Feature-first hexagonal architecture enforced by Import Linter contracts.
- Unit, end-to-end, contract, and Docker-backed integration tests.

## Tech Stack

| Area | Tooling |
| --- | --- |
| Runtime | Python 3.14, FastAPI, Uvicorn |
| Data validation | Pydantic 2, pydantic-settings |
| Persistence | PostgreSQL, SQLModel, SQLAlchemy, psycopg |
| Migrations | Alembic |
| Dependency management | uv |
| Testing | pytest, pytest-cov, pytest-html, testcontainers |
| Quality gates | Ruff, mypy, Import Linter, pre-commit |
| Containers | Docker, Docker Compose |
| Observability | Prometheus metrics, OpenTelemetry tracing, JSON logs |

## Project Structure

```text
.
├── alembic/                         # Alembic environment and migrations
├── docs/                            # Project documentation
├── src/
│   ├── main.py                      # Application composition entrypoint
│   ├── platform/                    # Shared platform code, no feature imports
│   │   ├── api/                     # App factory, middleware, errors, DI helpers
│   │   ├── config/                  # pydantic-settings configuration
│   │   ├── persistence/             # Shared persistence protocols/helpers
│   │   └── shared/                  # Cross-feature ports and Result helpers
│   └── features/
│       ├── _template/               # Inert scaffold for new features
│       └── kanban/                  # Active Kanban feature
│           ├── domain/              # Pure business model and specifications
│           ├── application/         # Commands, queries, ports, use cases
│           ├── adapters/            # HTTP and persistence adapters
│           ├── composition/         # Feature container and route wiring
│           └── tests/               # Feature-local tests and fakes
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
- Docker if you want the bundled PostgreSQL database or integration tests.

Start the API with a local PostgreSQL container:

```bash
cp .env.example .env
uv sync
docker compose up -d db
uv run alembic upgrade head
make dev
```

Then open:

- `http://localhost:8000/` for the root service response.
- `http://localhost:8000/health/live` for liveness.
- `http://localhost:8000/health/ready` for readiness.
- `http://localhost:8000/metrics` for Prometheus metrics.
- `http://localhost:8000/docs` for Swagger UI when `APP_ENABLE_DOCS=true`.

Create a board:

```bash
curl -s -X POST http://localhost:8000/api/boards \
  -H 'Content-Type: application/json' \
  -d '{"title":"Roadmap"}'
```

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
`src.platform.config.settings.AppSettings`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `development` | Must be `development`, `test`, or `production`. Trusted host middleware is enabled outside development. |
| `APP_ENABLE_DOCS` | `true` | Enables `/docs`, `/redoc`, and `/openapi.json`. Set `false` to disable all three. |
| `APP_CORS_ORIGINS` | `["*"]` | JSON list of allowed CORS origins. `["*"]` is treated as any origin. |
| `APP_TRUSTED_HOSTS` | `["*"]` | Hosts allowed by `TrustedHostMiddleware` outside development. |
| `APP_LOG_LEVEL` | `INFO` | Root Python log level. |
| `APP_POSTGRESQL_DSN` | `postgresql+psycopg://postgres:postgres@localhost:5432/kanban` | PostgreSQL DSN used by the app and Alembic. |
| `APP_HEALTH_PERSISTENCE_BACKEND` | `postgresql` | Label returned in `/health` under `persistence.backend`. |
| `APP_METRICS_ENABLED` | `true` | Exposes Prometheus metrics at `/metrics`. |
| `APP_OTEL_EXPORTER_ENDPOINT` | unset | Enables OpenTelemetry tracing over OTLP/HTTP. |
| `APP_OTEL_SERVICE_NAME` | `starter-template-fastapi` | Service name attached to traces and JSON logs. |
| `APP_OTEL_SERVICE_VERSION` | `0.1.0` | Service version attached to traces and JSON logs. |
| `APP_WRITE_API_KEY` | unset | Optional API key for write endpoints. When set, clients must send `X-API-Key`. |
| `POSTGRES_USER` | `postgres` | Docker Compose database user. |
| `POSTGRES_PASSWORD` | `postgres` | Docker Compose database password. |
| `POSTGRES_DB` | `kanban` | Docker Compose database name. |
| `APP_POSTGRESQL_DSN_DOCKER` | `postgresql+psycopg://postgres:postgres@db:5432/kanban` | Docker Compose DSN used by the app and migrate services. |

## Running Locally

Run with auto-reload on the host:

```bash
make dev
```

Run a production-style Uvicorn server locally after applying migrations:

```bash
uv run alembic upgrade head
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Run the app and database through Docker Compose:

```bash
docker compose up --build
```

Compose builds the Dockerfile `dev` target, runs a one-shot `migrate` service
with `alembic upgrade head`, then starts the app service with Uvicorn reload and
bind-mounted `src/` and `alembic/` directories.

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

The runtime image default command starts Uvicorn and does not run migrations.

## Deployment Notes

- Provision PostgreSQL before starting the app.
- Set `APP_POSTGRESQL_DSN` to the production database DSN.
- Run `alembic upgrade head` before starting the production app container.
- Set `APP_ENVIRONMENT=production` outside local development.
- Set `APP_ENABLE_DOCS=false` if Swagger UI and ReDoc should not be public.
- Set `APP_TRUSTED_HOSTS` to the public hostnames accepted by the service.
- Set `APP_CORS_ORIGINS` to explicit browser origins instead of `["*"]` for
  production browser clients.
- Set `APP_WRITE_API_KEY` if write endpoints should require `X-API-Key`.
- Use `/health/live` for liveness checks and `/health/ready` for readiness
  checks.

## Common Commands

| Command | Purpose |
| --- | --- |
| `make sync` | Install dependencies with `uv sync`. |
| `make dev` | Run the API with FastAPI auto-reload. |
| `make format` | Format code with Ruff. |
| `make lint` | Run Ruff lint checks. |
| `make lint-arch` | Run Import Linter architecture contracts. |
| `make typecheck` | Run mypy. |
| `make quality` | Run lint, architecture lint, and type checks. |
| `make test` | Run non-integration tests. |
| `make test-integration` | Run Docker-backed integration tests. |
| `make test-e2e` | Run end-to-end HTTP tests. |
| `make test-feature FEATURE=kanban` | Run tests for one feature. |
| `make cov` | Run tests with terminal coverage. |
| `make report` | Generate HTML test and coverage reports under `reports/`. |
| `make clean-reports` | Remove generated report artifacts. |
| `make ci` | Run the full local gate. |

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `make dev` cannot connect to PostgreSQL | Start `docker compose up -d db` or set `APP_POSTGRESQL_DSN` to a reachable database. |
| `docker compose up --build` exits before the app starts | Check the `migrate` service logs; the app waits for migrations to complete successfully. |
| `uv run alembic upgrade head` uses the wrong database | Check `APP_POSTGRESQL_DSN`; Alembic reads it before the default in `AppSettings`. |
| Write requests return `401` | Send `X-API-Key: <APP_WRITE_API_KEY>` or unset `APP_WRITE_API_KEY` for local development. |
| Requests return `422` for path IDs | Path IDs are parsed as UUIDs by FastAPI. Use valid UUID strings. |
| `/health/ready` returns `503` | A readiness dependency failed. Check database, Redis, and auth configuration. |
| Integration tests are skipped | Docker is unavailable or `KANBAN_SKIP_TESTCONTAINERS=1` is set. |
| Architecture lint fails | Check imports against the layer contracts in `pyproject.toml`. |

## Contribution Notes

There is no separate `CONTRIBUTING.md` in this repository. Follow these rules for
changes:

- Keep platform code independent from feature packages.
- Keep domain code free of FastAPI, Pydantic, SQLModel, SQLAlchemy, Alembic, and
  other adapter concerns.
- Keep application code free of FastAPI, SQLModel, SQLAlchemy, Alembic, and
  adapter concerns.
- Add new feature code under `src/features/<feature_name>/`.
- Put feature tests next to the feature under `src/features/<feature_name>/tests/`.
- Run `make quality` and `make test` before opening a pull request.
- Run `make test-integration` when persistence behavior changes.
