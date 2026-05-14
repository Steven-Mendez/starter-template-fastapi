## Why

Two runtime-dep hygiene issues, plus the cross-cluster requirement from `add-worker-image-target` for a clean api/worker dep split:

1. **`httpx` is in `[project] dependencies` (`pyproject.toml:14`) but is only used by tests (via `fastapi[standard]` TestClient) and the Resend email adapter at runtime.** Deployments that don't use Resend ship an unneeded HTTP client.
2. **`python-multipart~=0.0.20` (`pyproject.toml:25`) is pinned directly AND implied by `fastapi[standard]`.** Two version-bump surfaces, two Renovate PRs per release.
3. **The worker image needs only `arq`/`redis`, not `fastapi[standard]`; the API image needs `fastapi[standard]`, not `arq`'s client noise.** Today everything is in `[project] dependencies`, so both Docker stages pull both sets.

## What Changes

- Split `pyproject.toml` into `core` + extras:
  - Keep the minimal cross-cutting deps in `[project] dependencies` (pydantic, sqlmodel, alembic, argon2, etc. — the modules every layer needs).
  - Add `[project.optional-dependencies] api = ["fastapi[standard]>=..."]`.
  - Add `[project.optional-dependencies] worker = ["arq>=...", "redis>=..."]`.
  - Add `[project.optional-dependencies] resend = ["httpx>=0.28.1"]`.
  - Add `[project.optional-dependencies] s3 = ["boto3>=..."]` (mirror the pattern; already-optional adapter).
- Delete `python-multipart~=0.0.20` from `[project] dependencies`; it now comes transitively via `fastapi[standard]` in the `api` extra.
- Document install patterns in `docs/operations.md`:
  - API host: `uv sync --extra api` (+ `--extra resend` if using Resend, `--extra s3` if using S3).
  - Worker host: `uv sync --extra worker` (+ same optional extras).
  - Local dev: `uv sync --extra api --extra worker --extra resend --extra s3` (or the existing `dev` dependency-group, which already pulls in test tooling).
- The Resend adapter's composition raises a clear startup error referencing the `resend` extra if `httpx` is missing.

**Capabilities — Modified**: `quality-automation`.

## Impact

- **Code**: `pyproject.toml`, `Dockerfile` (consumed by `add-worker-image-target`), `docs/operations.md`.
- **Image size**: smaller default per-role images; the API image drops `arq`/`redis`, the worker image drops `fastapi[standard]`.
- **Backwards compatibility**: deployments using `uv sync` with no extras must now pick at least `--extra api` or `--extra worker`. Flagged in changelog and `docs/operations.md`.
