## Context

Multi-stage Dockerfiles often grow a per-process target so each role (API, worker, migration runner) ships a small image with the right `CMD`. This is the minimum increment: one new stage; same artifacts; different entrypoint.

## Decisions

- **Stage extends `runtime`, not from scratch**: keeps base layer + Python + the app code identical between API and worker. Only the `CMD` (and `HEALTHCHECK`) diverges. The new stage is declared `FROM runtime AS runtime-worker` so it inherits every layer added by `harden-dockerfile` (digest-pinned base, UID/GID 10001, tini entrypoint).
- **No worker-specific extra deps**: the runtime extras are a superset of what the worker needs; smaller marginal cost than maintaining two dep manifests.
- **HEALTHCHECK strategy**: the API-image HEALTHCHECK (curl `/health/live`) is removed in the worker stage. A worker-specific check (`redis-cli ping`) is optional and gated on `redis-cli` being available; otherwise the stage drops the HEALTHCHECK entirely and relies on the orchestrator's exit-code-based health.

## Ordering

This change **rebases on top of `harden-dockerfile`**:

1. `harden-dockerfile` lands first — it pins the base image by digest, sets explicit UID/GID 10001, installs `tini`, and tightens `.dockerignore`.
2. `add-worker-image-target` lands second — adds the `runtime-worker` stage that reuses the same base layers and only overrides the `CMD`.
3. `add-graceful-shutdown` lands third — appends `--timeout-graceful-shutdown 30` to the uvicorn `CMD` in `runtime`; the worker stage receives the matching `on_shutdown` hook in `src/worker.py`.
4. `harden-ci-security` then scans both images (Trivy + SBOM).

## Risks / Trade-offs

- **Risk**: API-only deps (e.g. uvicorn) bloat the worker image. Mitigation: acceptable; they're already in the shared `runtime` stage. Splitting deps is a bigger refactor for marginal MB savings (and `trim-runtime-deps` may yet do that work).

## Depends on

- `harden-dockerfile` — the worker stage extends the hardened `runtime` base.

## Conflicts with

- `Dockerfile` is shared with `harden-dockerfile`, `add-graceful-shutdown`, `trim-runtime-deps`. Rebase order documented above.
- `harden-ci-security` explicitly references this change ("Also scan the worker image once `add-worker-image-target` lands."). The CI scan job should run against both `runtime` and `runtime-worker`.
- `Makefile` is shared with `speed-up-ci` and `add-outbox-retention-prune`; the new `make docker-build-worker` target should be added with `.PHONY` parity.

## Migration

Single PR. Rollback: drop the stage.
