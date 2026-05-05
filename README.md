# starter-template-fastapi

Minimal [FastAPI](https://fastapi.tiangolo.com/) service with Uvicorn, OpenAPI docs at `/docs`, and a `/health` liveness route.

## Quick start

```bash
uv sync
docker compose up -d db
uv run alembic upgrade head
make dev   # uv run fastapi dev
```

Then open http://127.0.0.1:8000/docs for the interactive API docs.

## Requirements

- Python 3.14+ (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) for dependencies and `uv run`
- [GNU Make](https://www.gnu.org/software/make/) if you use the Makefile shortcuts below
- Docker (required for PostgreSQL containers)

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
make lint-arch # import-linter (hexagonal contracts)
make lint-fix # ruff checks + autofix
make typecheck  # mypy
make check    # lint + lint-arch + typecheck
make precommit-install
make precommit-run
make precommit-update
PORT=9000 make dev
```

## Run (without Make)

Development server with auto-reload via the FastAPI CLI:

```bash
uv run fastapi dev src/main.py
```

Production server:

```bash
uv run fastapi run src/main.py --host 0.0.0.0 --port 8000
```

The entrypoint is declared in `pyproject.toml` under `[tool.fastapi]`. Plain
`uvicorn src.main:app --reload` continues to work too.

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

## Conformance

Architecture conformance is enforced by import contracts (Import Linter).

Run the conformance gate:

```bash
uv run lint-imports
```

If it fails, fix the boundary violation in the owning layer (API, application,
domain, or infrastructure) instead of bypassing the check.

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
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Run full stack in Docker (app + PostgreSQL)

```bash
docker compose up --build
```

The API is exposed at http://127.0.0.1:8000 and uses the internal Compose DSN (`db:5432`).

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

## Add a new feature

Copy `src/features/_template/` and follow its [README](src/features/_template/README.md).
The Kanban feature (`src/features/kanban/`) is the canonical worked example for
every step.

## Project layout (feature-first)

```
src/
  main.py                       # composition root: builds platform + registers features
  platform/                     # cross-feature infra (no business logic)
    config/settings.py
    api/{app_factory,error_handlers,root,middleware/,dependencies/}
    persistence/{readiness,lifecycle,sqlmodel/engine}
    shared/{result, clock_port, id_generator_port, adapters/}
  features/
    kanban/                     # canonical example feature
      domain/                   # pure: aggregates, value objects, specs, errors
      application/
        ports/{inbound,outbound}/
        commands/, queries/, contracts/, errors.py, use_cases/
      adapters/
        inbound/http/           # routers, schemas, mappers, errors
        outbound/{persistence/sqlmodel, query}/
      composition/              # KanbanContainer + register_kanban
```

Architecture conformance is enforced by [import-linter](https://import-linter.readthedocs.io/)
contracts in `pyproject.toml`. See `hex-design-guide.md` for the full set of
boundaries and rationale.

### Migration from layer-first

The previous version of this template used `src/{api,application,domain,infrastructure}`.
Old imports map to:

| Old path                                                                  | New path                                                       |
|---------------------------------------------------------------------------|----------------------------------------------------------------|
| `src.domain.kanban.*`                                                     | `src.features.kanban.domain.*`                                 |
| `src.domain.shared.result`                                                | `src.platform.shared.result`                                   |
| `src.application.use_cases.*`                                             | `src.features.kanban.application.use_cases.*`                  |
| `src.application.commands.*` / `queries.*` / `contracts.*` / `kanban.errors` | `src.features.kanban.application.{commands,queries,contracts,errors}` |
| `src.application.ports.kanban_*` / `unit_of_work_port`                    | `src.features.kanban.application.ports.outbound.*`             |
| `src.application.ports.{clock,id_generator}_port`                         | `src.platform.shared.{clock,id_generator}_port`                |
| `src.application.shared.readiness`                                        | `src.platform.persistence.readiness`                           |
| `src.api.routers.*` / `schemas.*` / `mappers.kanban.*`                    | `src.features.kanban.adapters.inbound.http.*`                  |
| `src.infrastructure.adapters.outbound.persistence.sqlmodel.*`             | `src.features.kanban.adapters.outbound.persistence.sqlmodel.*` |
| `src.infrastructure.adapters.outbound.query.*`                            | `src.features.kanban.adapters.outbound.query.*`                |
| `src.infrastructure.adapters.outbound.{clock,id_generator}.*`             | `src.platform.shared.adapters.{system_clock,uuid_id_generator}`|
| `src.infrastructure.config.settings`                                      | `src.platform.config.settings`                                 |

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
