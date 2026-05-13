## ADDED Requirements

### Requirement: Documented setup sequence boots a runnable dev server on a clean checkout

The repository SHALL ship dev dependencies and example configuration such that the documented Setup-and-Development command sequence in `CLAUDE.md` produces a runnable FastAPI server with no further manual edits required.

Concretely, after running the documented sequence from a fresh clone (`cp .env.example .env`, `uv sync`, `docker compose up -d db`, `uv run alembic upgrade head`, `make dev`):

- The `fastapi` CLI binary used by `make dev` MUST be installed by `uv sync` (i.e. `fastapi[standard]` MUST be declared in the `dev` dependency group of `pyproject.toml`).
- The FastAPI lifespan startup MUST complete successfully — no required env var raised by any feature's composition root may be unset in `.env.example`. In particular, `APP_STORAGE_LOCAL_PATH` MUST have a default value in `.env.example` because `build_file_storage_container` requires it when `APP_STORAGE_BACKEND=local` (the default backend).
- The default storage path provided in `.env.example` MUST point inside the repo (e.g. `./var/storage`), and the parent directory pattern MUST be covered by `.gitignore`.

#### Scenario: `uv sync` installs the `fastapi` CLI binary

- **GIVEN** a fresh checkout
- **WHEN** the contributor runs `uv sync`
- **THEN** `uv run fastapi --version` exits with status 0 and prints a version string

#### Scenario: `make dev` boots without manual `.env` edits

- **GIVEN** a fresh checkout with the documented setup sequence completed (`cp .env.example .env && uv sync && docker compose up -d db && uv run alembic upgrade head`)
- **WHEN** the contributor runs `make dev`
- **THEN** the process logs `Uvicorn running on http://0.0.0.0:8000` (or the configured port) within the startup-timeout budget
- **AND** the process does not log any `RuntimeError` from a feature composition root
- **AND** in particular it does not raise `APP_STORAGE_LOCAL_PATH is required when APP_STORAGE_BACKEND=local`

#### Scenario: Default storage path is repo-local and ignored by git

- **GIVEN** the value of `APP_STORAGE_LOCAL_PATH` from a freshly copied `.env.example`
- **WHEN** the path is resolved against the repo root
- **THEN** it points inside the repository working tree (e.g. `./var/storage`)
- **AND** `git status` after a boot that wrote to that path lists no untracked files under that directory (the path or its parent is covered by `.gitignore`)
