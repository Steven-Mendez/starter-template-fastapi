## 1. Split into core + api + worker + resend + s3

- [ ] 1.1 In `pyproject.toml`, audit `[project] dependencies` and move everything not strictly needed by the domain/application layers into the appropriate extra.
- [ ] 1.2 Remove `"httpx>=0.28.1"` from `[project] dependencies`.
- [ ] 1.3 Remove `"python-multipart~=0.0.20"` from `[project] dependencies`.
- [ ] 1.4 Remove `"fastapi[standard]>=..."` from `[project] dependencies` (move to `api` extra).
- [ ] 1.5 Remove `"arq>=..."` and `"redis>=..."` from `[project] dependencies` (move to `worker` extra).

## 2. Declare extras

- [ ] 2.1 Add `[project.optional-dependencies] api = ["fastapi[standard]>=<current pin>"]`.
- [ ] 2.2 Add `[project.optional-dependencies] worker = ["arq>=<current pin>"]`. (Note: `arq` already depends on `redis>=4`; declare `redis` here only if you need to pin a version above what `arq` requires — otherwise the transitive resolution is fine.)
- [ ] 2.3 Add `[project.optional-dependencies] resend = ["httpx>=0.28.1"]`.
- [ ] 2.4 Add `[project.optional-dependencies] s3 = ["boto3>=<current pin>"]` (mirror the pattern for the already-optional S3 adapter).

## 3. Composition guards

- [ ] 3.1 Confirm the Resend adapter's composition raises a clear startup error naming the `resend` extra if `httpx` is missing. Add the guard if absent.
- [ ] 3.2 Confirm the same pattern for the S3 adapter (`boto3` missing → `s3` extra named in the error).

## 4. Dockerfile

- [ ] 4.1 In the `runtime-api` build stage, invoke `uv sync --extra api` (+ `--extra resend` / `--extra s3` conditionally on build args).
- [ ] 4.2 Coordinate with `add-worker-image-target`: the `runtime-worker` stage invokes `uv sync --extra worker` (+ optional extras). Land this change before or alongside `add-worker-image-target`.

## 5. Verify

- [ ] 5.1 `uv sync` (no extras) — confirm `httpx`, `fastapi`, `arq` are absent.
- [ ] 5.2 `uv sync --extra api` — confirm `fastapi[standard]` and `python-multipart` are present, `arq` absent.
- [ ] 5.3 `uv sync --extra worker` — confirm `arq` and `redis` present, `fastapi[standard]` absent.
- [ ] 5.4 `uv sync --extra resend` — confirm `httpx` present.
- [ ] 5.5 Build both Docker stages; confirm the API image lacks `arq` and the worker image lacks `fastapi[standard]`.
- [ ] 5.6 `make ci` green.

## 6. Docs

- [ ] 6.1 Update `docs/operations.md` with the install matrix per role/backend.
- [ ] 6.2 Note in the changelog that `uv sync` with no extras no longer works for a running deployment.
