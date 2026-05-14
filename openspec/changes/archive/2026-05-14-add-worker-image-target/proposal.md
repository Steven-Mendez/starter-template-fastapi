## Why

The `Dockerfile` has `dev` and `runtime` (uvicorn) stages but no `runtime-worker` stage. `make worker` runs `python -m worker`; deploying that in K8s requires reusing the API image and overriding `CMD`. Easy to forget; risks shipping a "worker pod" that secretly runs uvicorn (or vice versa).

## What Changes

- Add a `runtime-worker` stage in `Dockerfile` that `FROM runtime AS runtime-worker` — reuses every layer from the hardened API runtime and only overrides:
  - `CMD ["python", "-m", "worker"]`.
  - Removes the API `HEALTHCHECK` (optionally replaces with `redis-cli ping` when available).
- Add `make docker-build-worker` invoking `docker build --target runtime-worker --tag worker:latest .`.
- Document the build pattern in `docs/operations.md` (`--target runtime` vs `--target runtime-worker`).

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code**:
  - `Dockerfile` — new stage `runtime-worker`.
  - `Makefile` — new `docker-build-worker` target.
  - `docs/operations.md` — two-image build pattern documented.
- **CI**: extends `harden-ci-security` so Trivy scans both images.
- **Production**: deployments now have a clear two-image pattern.
