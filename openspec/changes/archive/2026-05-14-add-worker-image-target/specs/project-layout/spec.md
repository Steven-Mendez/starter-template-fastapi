## ADDED Requirements

### Requirement: Dockerfile exposes a dedicated worker stage

The `Dockerfile` SHALL define a `runtime-worker` stage declared as `FROM runtime AS runtime-worker`, so it inherits every layer of the hardened `runtime` base (digest-pinned base image, UID/GID 10001, tini entrypoint). Only `CMD` (and optionally `HEALTHCHECK`) SHALL differ from the `runtime` stage.

A `Makefile` target `docker-build-worker` SHALL invoke `docker build --target runtime-worker --tag worker:latest .`. `docs/operations.md` SHALL document the two-image build pattern (API target vs worker target).

#### Scenario: Worker image starts the arq worker

- **GIVEN** an image built with `--target runtime-worker`
- **WHEN** the container starts
- **THEN** the process invokes the arq worker (process tree includes `python -m worker` or equivalent)
- **AND** the process does NOT invoke uvicorn

#### Scenario: Worker image reuses the hardened base

- **GIVEN** an image built with `--target runtime-worker`
- **WHEN** `id -u` is shelled inside the container
- **THEN** the output is `10001` (same as the API runtime image)
- **AND** PID 1 is `tini`

#### Scenario: Worker image omits the API HTTP HEALTHCHECK

- **GIVEN** an image built with `--target runtime-worker`
- **WHEN** the image metadata is inspected (`docker inspect --format '{{json .Config.Healthcheck}}'`)
- **THEN** no HEALTHCHECK that probes `http://localhost:8000/health/live` is defined
- **AND** the container does not bind a TCP listener on `8000`
