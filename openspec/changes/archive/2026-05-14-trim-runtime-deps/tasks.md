## 1. Split into core + api + worker + resend + s3

- [x] 1.1 In `pyproject.toml`, audit `[project] dependencies` and move everything not strictly needed by the domain/application layers into the appropriate extra.
- [x] 1.2 Remove `"httpx>=0.28.1"` from `[project] dependencies`.
- [x] 1.3 Remove `"python-multipart~=0.0.20"` from `[project] dependencies`.
- [x] 1.4 Remove `"fastapi[standard]>=..."` from `[project] dependencies` (move to `api` extra).
- [x] 1.5 Remove `"arq>=..."` and `"redis>=..."` from `[project] dependencies` (move to `worker` extra).

## 2. Declare extras

- [x] 2.1 Add `[project.optional-dependencies] api = ["fastapi[standard]>=<current pin>"]`.
- [x] 2.2 Add `[project.optional-dependencies] worker = ["arq>=<current pin>"]`. (Note: `arq` already depends on `redis>=4`; declare `redis` here only if you need to pin a version above what `arq` requires — otherwise the transitive resolution is fine.)
- [x] 2.3 Add `[project.optional-dependencies] resend = ["httpx>=0.28.1"]`.
- [x] 2.4 Add `[project.optional-dependencies] s3 = ["boto3>=<current pin>"]` (mirror the pattern for the already-optional S3 adapter).

## 3. Composition guards

- [x] 3.1 Confirm the Resend adapter's composition raises a clear startup error naming the `resend` extra if `httpx` is missing. Add the guard if absent.
- [x] 3.2 Confirm the same pattern for the S3 adapter (`boto3` missing → `s3` extra named in the error).

## 4. Dockerfile

- [x] 4.1 In the `runtime-api` build stage, invoke `uv sync --extra api` (+ `--extra resend` / `--extra s3` conditionally on build args).
- [x] 4.2 Coordinate with `add-worker-image-target`: the `runtime-worker` stage invokes `uv sync --extra worker` (+ optional extras). Land this change before or alongside `add-worker-image-target`.

## 5. Verify

- [x] 5.1 `uv sync` (no extras) — confirm `httpx`, `fastapi`, `arq` are absent.
- [x] 5.2 `uv sync --extra api` — confirm `fastapi[standard]` and `python-multipart` are present, `arq` absent.
- [x] 5.3 `uv sync --extra worker` — confirm `arq` and `redis` present, `fastapi[standard]` absent.
- [x] 5.4 `uv sync --extra resend` — confirm `httpx` present.
- [x] 5.5 Build both Docker stages; confirm the API image lacks `arq` and the worker image lacks `fastapi[standard]`.
- [x] 5.6 `make ci` green.

## 6. Docs

- [x] 6.1 Update `docs/operations.md` with the install matrix per role/backend.
- [x] 6.2 Note in the changelog that `uv sync` with no extras no longer works for a running deployment.
