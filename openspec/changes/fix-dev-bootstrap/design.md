## Context

`CLAUDE.md` advertises a clone-and-run flow: copy `.env.example`, `uv sync`, bring Postgres up, run migrations, `make dev`. In practice, running that sequence against the current `main` produces two consecutive failures:

1. `make dev` → `uv run fastapi dev …` → `RuntimeError: To use the fastapi command, please install "fastapi[standard]"`. The project's `[project] dependencies` list only `fastapi` (no extras); `fastapi[standard]` is never installed because nothing declares it.
2. Substituting `python -m uvicorn` to bypass (1) reveals a second blocker: lifespan startup raises `RuntimeError: APP_STORAGE_LOCAL_PATH is required when APP_STORAGE_BACKEND=local` from `src/features/file_storage/composition/container.py:35`. The file-storage container is always built (deliberate, per the module docstring) and validates the path for the default `local` backend. `.env.example` does not provide a default for that path.

These were observed live during a session that ran the documented commands verbatim and had to add `APP_STORAGE_LOCAL_PATH=/tmp/starter-template-storage` plus `python -m uvicorn` invocations to get a server up.

## Goals / Non-Goals

**Goals:**
- A fresh clone + the documented setup sequence in `CLAUDE.md` produces a running dev server with zero manual `.env` edits and zero `pip install` / `uv add` workarounds.
- Keep all existing production-safety validation intact. The fix lives in dev dependencies and example config, not in feature code.
- Provide a default `APP_STORAGE_LOCAL_PATH` that is safe by default: inside the repo (so it doesn't pollute the user's `$HOME` or `/tmp`) and ignored by git (so the test fixtures dev writes don't show up in `git status`).

**Non-Goals:**
- Restructuring the file-storage composition root to skip building the container when `APP_STORAGE_ENABLED=false`. That's a wider, behaviour-affecting change and the current "always-built" design is intentional.
- Introducing a `null` storage backend.
- Changing the production checklist or any validator behaviour.
- Pinning `fastapi[standard]` extras to a specific version range distinct from `fastapi` itself (uv resolves the extras against the same package version, so this is automatic).

## Decisions

### Decision 1: Add `fastapi[standard]` to the `dev` group, not to runtime `dependencies`

`fastapi[standard]` pulls in `watchfiles`, `python-multipart`, `httpx`, `email-validator`, `jinja2`, and `uvicorn[standard]`. Several of these are only needed for `fastapi dev` (auto-reload via watchfiles) and the FastAPI CLI itself. Runtime `dependencies` already pin `uvicorn` directly where production needs it.

- **Chosen**: `[dependency-groups] dev = [..., "fastapi[standard]>=…"]` matching the existing `fastapi` pin.
- **Rejected**: Promoting `fastapi[standard]` to runtime `dependencies`. It would bloat the production wheel for libraries the prod server (started via `fastapi run` or `uvicorn` directly) doesn't need.
- **Rejected**: Documenting "run `uv add fastapi[standard]` after `uv sync`". Defeats the point of `uv sync`-based onboarding.

### Decision 2: Default `APP_STORAGE_LOCAL_PATH=./var/storage` in `.env.example`

- **Chosen**: `./var/storage` (repo-relative), with `var/` added to `.gitignore`. Repo-relative keeps the path discoverable, scoped to the project, and trivially cleanable (`rm -rf var/`). It mirrors common conventions for runtime-state directories (`var/log`, `var/cache`).
- **Rejected**: `/tmp/starter-template-storage`. Survives only until reboot; tying dev state to `/tmp` is OS-dependent (Linux nukes `/tmp` on boot on many distros, macOS doesn't) and complicates testing of write-then-read flows across runs.
- **Rejected**: `~/.local/share/starter-template-fastapi/storage`. Pollutes the user's home; harder to wipe; surprising when a `git pull` would conceptually want to reset state.
- **Rejected**: Removing the default and instead making `build_file_storage_container` tolerate a missing path when `enabled=false`. Behavioural change to a feature whose docstring explicitly states the container is always built; out of scope per Non-Goals.

### Decision 3: No production-checklist change

`AppSettings.validate_production` (via `StorageSettings.validate_production`) already refuses `APP_STORAGE_BACKEND=local` when `APP_STORAGE_ENABLED=true` in production. The new default in `.env.example` is `APP_STORAGE_LOCAL_PATH=./var/storage`, but production deployments override the whole storage stack to `s3` anyway. No new check needed.

## Risks / Trade-offs

- **Risk**: `fastapi[standard]` upgrades may drift independently of `fastapi`. → Mitigation: declare with the same lower-bound version constraint as the base `fastapi` dep; Renovate's `fastapi`+`starlette`+`pydantic` group (added by `add-quality-automation`) keeps the two co-versioned on bumps.
- **Risk**: Adding `var/` to `.gitignore` could mask intentional `var/`-named files added later (e.g. a `var/sql.go` if the project ever cross-languages). → Mitigation: scope to `var/` (trailing slash) so only directories match; revisit if a file collision shows up.
- **Trade-off**: Choosing repo-local over `/tmp` means the writable directory ships with the repo. Per Decision 2 the trade is worth it for discoverability + portability.

## Migration Plan

Single PR. Steps:

1. Update `pyproject.toml` `[dependency-groups] dev` to include `fastapi[standard]`.
2. Update `.env.example` to include `APP_STORAGE_LOCAL_PATH=./var/storage` with a one-line comment.
3. Add `var/` to `.gitignore` (verify it's not already there).
4. Re-run `uv sync` to refresh the lockfile and CI image.
5. Manual verification: `cp .env.example .env && uv sync && make dev` from a clean checkout boots successfully (one of the tasks in `tasks.md`).

No rollback complexity — purely additive to dev tooling. If `fastapi[standard]` causes a CI regression, the existing `make ci` would surface it before merge.
