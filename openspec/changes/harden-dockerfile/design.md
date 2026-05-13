## Context

Dockerfile hardening is a checklist exercise; this proposal walks through the four canonical items missing from the current multi-stage image (`dev` + `runtime`).

## Decisions

- **Extend the existing multi-stage Dockerfile, don't rewrite**: every change here is a layer added to the existing `runtime` stage (or `.dockerignore` line additions). No stage renames, no rebases of the dev stage.
- **UID/GID 10001**: well-above-default UID so we won't collide with system users in any common base image; documented as the contract for K8s `runAsUser` / `fsGroup`.
- **tini, not dumb-init**: both are fine; tini is the Docker-blessed reference and is in Debian apt repos. Pairs with `add-graceful-shutdown` so SIGTERM is forwarded to uvicorn / arq.
- **Digest pinning over `:3.12-slim`**: tag pins are convenient but allow re-tagging; digests are immutable and Renovate handles bumps.

## Ordering

This change lands **first** in the Dockerfile cluster:

1. `harden-dockerfile` (this change) — pins digests, sets UID/GID 10001, installs `tini`, tightens `.dockerignore`.
2. `add-worker-image-target` — rebases on top by adding `FROM runtime AS runtime-worker`.
3. `add-graceful-shutdown` — appends `--timeout-graceful-shutdown 30` to the uvicorn `CMD` in the hardened `runtime` stage.
4. `trim-runtime-deps` — independently shrinks deps; can land any time but conflicts in `pyproject.toml` mean it usually goes last.

## Risks / Trade-offs

- **Risk**: a digest pin masquerading as the wrong image. Mitigation: digests are content-addressed; we trust the registry's hash.
- **Trade-off**: more bytes in the Dockerfile. Negligible.

## Depends on

- None.

## Conflicts with

- `Dockerfile` is shared with `add-worker-image-target`, `add-graceful-shutdown`, `trim-runtime-deps`. Rebase order above.
- `renovate.json` is shared with `tighten-renovate-policy`; the new `updatePinnedDependencies: true` rule must be merged with the policies that change lands.

## Migration

Single PR. Rollback: revert.
