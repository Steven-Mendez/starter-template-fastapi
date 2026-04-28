# starter-template-fastapi

Minimal [FastAPI](https://fastapi.tiangolo.com/) service with Uvicorn, OpenAPI docs at `/docs`, and a `/health` liveness route.

## Quick start

```bash
uv sync
docker compose up -d db
uv run alembic upgrade head
make dev
```

Then open http://127.0.0.1:8000/docs for the interactive API docs.

## Requirements

- Python 3.14+ (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) for dependencies and `uv run`
- [GNU Make](https://www.gnu.org/software/make/) if you use the Makefile shortcuts below
- Docker (required for PostgreSQL containers and integration/e2e tests)

## Install

With uv:

```bash
uv sync
```

Add or upgrade dependencies (preferred over editing `pyproject.toml` by hand):

```bash
uv add <package>
uv add 'some-package[extra]'   # extras in quotes
```

With pip (virtual environment recommended):

```bash
pip install -e .
```

## Make (shortcuts)

```bash
make          # list targets (default)
make sync     # uv sync — install from lockfile
make dev      # dev server with reload (default port 8000)
make format   # ruff formatter
make lint     # ruff checks
make lint-fix # ruff checks + autofix
make typecheck  # mypy
make check    # lint + typecheck
make precommit-install
make precommit-run
make precommit-update
make test-fast
make test-cov  # coverage (non-e2e, fail under 90%)
PORT=9000 make dev
```

## Run (without Make)

Development server with auto-reload:

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If you use a globally installed Uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If your FastAPI install exposes the CLI:

```bash
fastapi run main.py
```

## Quality gates

Run linting and type checks directly:

```bash
uv run ruff check .
uv run mypy
```

or with Make:

```bash
make format
make lint
make lint-fix
make typecheck
make check
```

Install and run git hooks:

```bash
make precommit-install
make precommit-run
make precommit-update
```

Useful URLs (default port 8000):

- API: http://127.0.0.1:8000/
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health: http://127.0.0.1:8000/health

## Runtime settings

Environment variables use the `APP_` prefix:

- `APP_ENABLE_DOCS=true|false`
- `APP_ENVIRONMENT=development|test|production`
- `APP_CORS_ORIGINS='["https://frontend.example.com"]'`
- `APP_TRUSTED_HOSTS='["api.example.com"]'`
- `APP_POSTGRESQL_DSN=postgresql+psycopg://postgres:postgres@localhost:5432/kanban`

The application is PostgreSQL-only.

## Docker workflows

### Run PostgreSQL in Docker, app locally

1) Start only the database service:

```bash
docker compose up -d db
```

2) Run migrations against the local DSN (`localhost`):

```bash
uv run alembic upgrade head
```

3) Start the API locally:

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Run full stack in Docker (app + PostgreSQL)

```bash
docker compose up --build
```

The API is exposed at http://127.0.0.1:8000 and uses the internal Compose DSN (`db:5432`).

## Testing strategy

- Unit tests run against PostgreSQL testcontainers.
- Integration tests run against PostgreSQL via `testcontainers` and apply
  Alembic migrations before exercising API flows.
- E2E tests run a live Uvicorn process against PostgreSQL in Docker.

Run the default fast suite (unit + integration, skips e2e):

```bash
make test-fast
```

Run integration tests only (requires Docker):

```bash
make test-integration
```

If Docker is unavailable, integration tests are skipped automatically.

Run e2e tests:

```bash
make test-e2e
```

Run the full suite:

```bash
make test
```

## Database migrations (Alembic)

Run migrations:

```bash
uv run alembic upgrade head
```

Create a new revision (autogenerate):

```bash
uv run alembic revision --autogenerate -m "describe-change"
```

`GET /health` reports persistence readiness:

```json
{
  "status": "ok",
  "persistence": {
    "backend": "postgresql",
    "ready": true
  }
}
```

## Git

The root `.gitignore` keeps virtualenvs, caches, coverage output, and `.env` files out of Git. **Commit** `uv.lock` and `.python-version` for reproducible installs; put secrets in `.env` (ignored). You can commit a template as `.env.example` if you add one.

## OpenSpec

This repo uses [OpenSpec](https://github.com/Fission-AI/OpenSpec) for spec-driven changes.

- **Canonical requirements** live under `openspec/specs/` (e.g. `api-core`, `dev-makefile`, `repo-hygiene`).
- **Completed change folders** (proposal, design, delta specs, tasks) are under `openspec/changes/archive/`:
  - `2026-04-13-init-fastapi-project` — FastAPI app, dependencies, docs
  - `2026-04-13-makefile-dev-workflow` — root `Makefile` and dev shortcuts
  - `2026-04-13-improve-gitignore` — root `.gitignore` and Git hygiene notes
  - `2026-04-13-kanban-card-priority` — Kanban card `priority` field (`low` / `medium` / `high`)
  - `2026-04-13-add-optional-due-at-on-cards` — optional nullable `due_at` (ISO 8601) on cards

There are no active in-flight changes under `openspec/changes/` until you add a new one (for example `openspec new change "<name>"`).
