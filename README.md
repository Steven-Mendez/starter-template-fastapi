# starter-template-fastapi

Minimal [FastAPI](https://fastapi.tiangolo.com/) service with Uvicorn, OpenAPI docs at `/docs`, and a `/health` liveness route.

## Quick start

```bash
uv sync
make dev
```

Then open http://127.0.0.1:8000/docs for the interactive API docs.

## Requirements

- Python 3.14+ (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) for dependencies and `uv run`
- [GNU Make](https://www.gnu.org/software/make/) if you use the Makefile shortcuts below

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

Useful URLs (default port 8000):

- API: http://127.0.0.1:8000/
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health: http://127.0.0.1:8000/health

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

There are no active in-flight changes under `openspec/changes/` until you add a new one (for example `openspec new change "<name>"`).
