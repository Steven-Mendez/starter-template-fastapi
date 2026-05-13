## 1. Worker stage

- [ ] 1.1 In `Dockerfile`, add `FROM runtime AS runtime-worker` after the existing `runtime` stage.
- [ ] 1.2 Override `CMD ["python", "-m", "worker"]`.
- [ ] 1.3 Remove the API `HEALTHCHECK` from the worker stage (worker has no HTTP listener; rely on K8s `livenessProbe` against the worker process via `exec` instead). `redis-cli` is not on `python:3.12-slim` and pulling it in just for HEALTHCHECK is overkill.

## 2. Build automation

- [ ] 2.1 Add `docker-build-worker` recipe to `Makefile` invoking `docker build --target runtime-worker --tag worker:latest .`.
- [ ] 2.2 Add `docker-build-worker` to the `.PHONY` list in `Makefile`.
- [ ] 2.3 If CI already builds the API image (see `.github/workflows/`), add a parallel step that builds the worker target (`docker buildx … --target runtime-worker`).

## 3. Docs

- [ ] 3.1 Document the two-image pattern in `docs/operations.md` (API vs worker image; `--target` flags; K8s deployment shape).
- [ ] 3.2 `make ci` green.
