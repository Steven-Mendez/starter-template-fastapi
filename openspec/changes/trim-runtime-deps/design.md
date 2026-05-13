## Context

Templates accumulate "we might need it" deps. The pattern that works is `[project.optional-dependencies]` keyed on the feature that needs them. The Resend adapter is the only runtime consumer of `httpx`; the `arq` worker is the only runtime consumer of `arq`'s client/redis stack; the API process only needs `fastapi[standard]` and the shared core.

## Decisions

### Chosen direction: split into `core` + `api` + `worker` extras

`pyproject.toml` adopts:

- `[project] dependencies` becomes the minimal **core** set (everything the domain/application layers need: pydantic, sqlmodel, alembic, httpx for nothing — actually NO httpx, see below; argon2, etc.).
- `[project.optional-dependencies]`:
  - `api = ["fastapi[standard]>=..."]` — pulls in uvicorn, python-multipart, starlette extras.
  - `worker = ["arq>=...", "redis>=..."]` — pulls in the arq client + redis (Resend is OPTIONAL on the worker too; `worker` does not imply `resend`).
  - `resend = ["httpx>=0.28.1"]` — only the Resend email adapter.
  - `s3 = ["boto3>=..."]` — only the S3 file-storage adapter.

Rationale:

- The cross-cluster `add-worker-image-target` change introduces a separate `runtime-worker` Docker stage that should NOT pull in `fastapi[standard]`, and the `runtime-api` stage should NOT pull in `arq`.
- The `api` extra exists explicitly to support the dependency split that `add-worker-image-target` needs. We declare it here so that change does not also have to touch `pyproject.toml` for the dep names.
- `python-multipart` is dropped as a direct dependency — `fastapi[standard]` (via the `api` extra) already provides it. Single Renovate surface per release.
- `httpx` is dropped from the base `dependencies` — it is currently used only by the Resend adapter at runtime; tests get `httpx` via `fastapi[standard]` (TestClient) in the dev group.

### Rejected: keep everything in `[project] dependencies` and rely on Docker `--no-install-recommends`

That does not actually reduce the wheel set; it only affects Debian packages. The bloat is Python wheels.

## Non-goals

- Not pinning new versions; each extra keeps the current pin from `[project] dependencies`.
- Not introducing per-feature extras beyond `api`, `worker`, `resend`, `s3`.
- Not changing the `[dependency-groups] dev` set — local dev keeps a single fat install.
- Not rewriting any feature's import surface to support lazy imports beyond what's needed for the two composition guards (Resend, S3).
- Not splitting `pyproject.toml` into multiple files or workspaces.

## Risks / Trade-offs

- Deployments that previously ran `uv sync` (no extras) and used Resend will need to switch to `uv sync --extra api --extra resend`. Mitigation: the Resend adapter's composition raises a clear startup error naming the missing extra. Documented in `docs/operations.md`.
- More extras = more Renovate PR groups. Mitigation: `tighten-renovate-policy` groups all production deps together.

## Migration

Single PR. Rollback: revert `pyproject.toml`. Coordinate with `add-worker-image-target` so the Dockerfile changes that consume the new extras land together (or this lands first and the worker-image PR depends on it).

## Depends on

- None at the code level.

## Conflicts with

- Shares `pyproject.toml` with `enable-strict-mypy`, `expand-ruff-ruleset`, `harden-ci-security`, `add-error-reporting-seam`, `clean-architecture-seams` (top-of-file `[project]` table edits).
- Shares `Dockerfile` with `add-graceful-shutdown`, `harden-dockerfile`, `add-worker-image-target` (build-stage edits).

## Cross-cluster dependency

- **Enables `add-worker-image-target`**: the `worker` extra defined here is what the new `runtime-worker` Docker stage installs. Land this first (or together) so that change does not have to introduce its own dep split.
