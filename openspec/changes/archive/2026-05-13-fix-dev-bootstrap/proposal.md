## Why

The documented `Setup` and `Development` sequence in `CLAUDE.md` (`cp .env.example .env && uv sync` → `make dev`) does not produce a runnable server on a clean checkout. Two independent gaps surface back-to-back when a contributor (or AI agent) follows the README:

1. `make dev` invokes `uv run fastapi dev …`, but `fastapi[standard]` is not declared anywhere — the project only depends on bare `fastapi`. The CLI binary aborts with `RuntimeError: To use the fastapi command, please install "fastapi[standard]"`.
2. After bypassing (1) with raw uvicorn, lifespan startup fails with `RuntimeError: APP_STORAGE_LOCAL_PATH is required when APP_STORAGE_BACKEND=local` because `build_file_storage_container` validates the path unconditionally, regardless of `APP_STORAGE_ENABLED`. `.env.example` ships no default for the path.

Both are first-five-minutes papercuts on a project whose entire pitch is "clone-and-run starter template". Fixing them is purely additive to dev tooling and `.env.example`; no feature behavior or production code path changes.

## What Changes

- Add `fastapi[standard]` to the project's `dev` dependency group in `pyproject.toml` so `uv sync` installs the `fastapi` CLI, `watchfiles`, and `python-multipart` that `make dev` already assumes. Document the dependency in `CLAUDE.md` if it isn't already implicit.
- Add `APP_STORAGE_LOCAL_PATH=./var/storage` (and surrounding comments) to `.env.example` so a fresh checkout boots even with the default `APP_STORAGE_BACKEND=local`. Add `var/` to `.gitignore` if missing.
- No source-code changes to `build_file_storage_container` or `StorageSettings`: the current "always-built container, fail loudly on missing path" behavior is intentional architecture (see container.py module docstring) and we keep it. The fix is to provide a default path, not to weaken validation.
- No production-checklist changes: `APP_STORAGE_LOCAL_PATH` already has no production impact unless `APP_STORAGE_ENABLED=true`, in which case the production validator already refuses `local` backend.

**Out of scope:** Re-architecting the storage container to skip building when `APP_STORAGE_ENABLED=false`; adding a `null` storage backend. Both have wider blast radius and are not required to unblock onboarding.

## Capabilities

### New Capabilities
<!-- None — this is a dev-environment / onboarding fix, not a new product capability. -->

### Modified Capabilities
- `quality-automation`: Extend with a new requirement that the documented Setup-and-Dev command sequence boots a runnable server on a clean checkout (no missing CLI binaries, no missing required env vars). The existing branch-coverage, Renovate, and SHA-pinning requirements are unchanged.

## Impact

- **Code**: `pyproject.toml` (one dep added to the `dev` group), `.env.example` (one new line + comment), `.gitignore` (one line if `var/` not already ignored). Optional: a sentence in `CLAUDE.md` Setup.
- **Runtime / API / migrations**: none.
- **CI**: `make ci` is unaffected (it doesn't touch the `fastapi` CLI). Existing test suites and quality gates continue to pass.
- **Production**: none. The default `./var/storage` path is only consulted when `APP_STORAGE_ENABLED=true`, which is already refused by `validate_production` for the `local` backend.
- **Onboarding**: `cp .env.example .env && uv sync && docker compose up -d db && uv run alembic upgrade head && make dev` becomes a working sequence end-to-end.
