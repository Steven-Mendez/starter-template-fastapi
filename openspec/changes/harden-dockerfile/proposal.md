## Why

Four supply-chain / runtime defects in the production `Dockerfile`:

1. **Base images pinned by tag, not digest.** `python:3.12-slim` and `ghcr.io/astral-sh/uv:0.11.8` can silently change underneath us when the registry re-tags.
2. **Non-root user has an implicit UID/GID.** `addgroup --system app && adduser --system --ingroup app app` picks whatever the next free system UID is — unstable across base-image rebuilds; unfriendly to K8s `runAsUser`/`fsGroup`.
3. **No PID-1 signal forwarder.** `uvicorn` runs as PID 1; SIGTERM works but zombie child reaping (e.g. from `python -c` healthchecks) is not handled.
4. **`.dockerignore` is incomplete** — `var/`, `.github/`, `openspec/`, `scripts/`, `reports/`, `.DS_Store`, `*.log` are not ignored, bloating the build context.

## What Changes

- Pin both base images by `@sha256:…` digest (Renovate will manage them).
- Explicit `--gid 10001` / `--uid 10001` on the `app` user, documented to align with K8s `securityContext.runAsUser/fsGroup`.
- Add `tini` (via `apt-get install -y --no-install-recommends tini`) and set `ENTRYPOINT ["tini", "--"]`.
- Append `var/`, `.github/`, `openspec/`, `scripts/`, `reports/`, `.DS_Store`, `*.log` to `.dockerignore`.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code**: `Dockerfile`, `.dockerignore`.
- **CI**: `make docker-build` continues to work; Renovate will start managing the new digests.
- **K8s manifests** outside this repo: `runAsUser: 10001`, `fsGroup: 10001`.
