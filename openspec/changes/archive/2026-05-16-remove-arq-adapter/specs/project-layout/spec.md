## REMOVED Requirements

### Requirement: arq worker has bounded result retention with per-handler override

**Reason:** This requirement is wholly about the `arq` `WorkerSettings`
(`max_jobs`, `job_timeout`, `keep_result`, the `arq.worker.Function`
list) and the arq Redis `arq:queue:result:*` keys. With the `arq`
adapter and runtime removed (ROADMAP ETAPA I step 5) none of these
symbols or settings exist. Result-retention / timeout / max-jobs are
properties of a specific job runtime; they will be re-specified for the
AWS SQS + Lambda runtime at a later roadmap step (steps 26–27). Removed
here rather than left asserting deleted code.

## MODIFIED Requirements

### Requirement: Entrypoints reference modules by their real names

The system SHALL configure every entrypoint — FastAPI CLI, `uvicorn`, the Docker image, the Makefile, and the Alembic environment — to import modules by their post-refactor names (`main:app`, `worker`, `app_platform.X`, `features.X`) and SHALL NOT use the `src.` prefix. The `worker` module name SHALL remain valid: `src/worker.py` continues to exist as the runtime-agnostic composition-root scaffold (no `arq` import) until the production job runtime is added at a later roadmap step.

#### Scenario: FastAPI CLI entrypoint declares the bare module

- **WHEN** an operator inspects `pyproject.toml`
- **THEN** `[tool.fastapi]` declares `entrypoint = "main:app"` (no `src.` prefix)

#### Scenario: Docker image runs uvicorn against the bare module

- **WHEN** an operator inspects `Dockerfile`
- **THEN** every `CMD` that invokes `uvicorn` references `main:app` (not `src.main:app`), and the image either sets `ENV PYTHONPATH=src` or invokes uvicorn with `--app-dir src`

#### Scenario: Makefile invokes the worker by its bare module name

- **WHEN** an operator inspects `Makefile`
- **THEN** the `worker` target invokes `python -m worker` (not `python -m src.worker`), and the `outbox-retry-failed` target invokes `python -m features.outbox.management` with `PYTHONPATH=src` set in the environment
- **AND** the `worker` target's help text does not claim it runs an `arq` worker (the worker runtime is added at a later roadmap step)

#### Scenario: Alembic env imports models by their real names

- **WHEN** an operator inspects `alembic/env.py`
- **THEN** every model import references `features.X.adapters.outbound.persistence.sqlmodel.models` or `app_platform.persistence.sqlmodel.authorization.models` (no `src.` prefix), and the settings import is `from app_platform.config.settings import AppSettings`

### Requirement: Process shutdown is graceful and bounded

The API server SHALL be launched with `--timeout-graceful-shutdown` equal to `APP_SHUTDOWN_TIMEOUT_SECONDS` (default 30 s). On SIGTERM the FastAPI `lifespan` finalizer SHALL:

1. Clear the readiness flag so subsequent `/health/ready` probes return 503.
2. Drain in-flight requests up to `APP_SHUTDOWN_TIMEOUT_SECONDS` (uvicorn enforces this).
3. Dispose the SQLAlchemy engine.
4. Close the Redis client.
5. Call `provider.shutdown()` on the OTel `TracerProvider` to flush the `BatchSpanProcessor`.

Each finalizer step SHALL be wrapped in `try/except` + warn log so a slow step does not skip the others.

The future job runtime (AWS SQS + a Lambda worker, a later roadmap step) SHALL implement the equivalent drain — waiting for in-flight `DispatchPending.execute` ticks and active job handlers to complete (bounded by `APP_SHUTDOWN_TIMEOUT_SECONDS`) before disposing the engine and closing Redis. The reusable engine-dispose / Redis-close / tracing-flush helpers in `src/worker.py` SHALL remain available for that runtime to re-bind; no `arq` `on_shutdown` binding exists in the meantime.

#### Scenario: SIGTERM mid-request drains before exit

- **GIVEN** an API replica with an in-flight request expected to complete in less than `APP_SHUTDOWN_TIMEOUT_SECONDS`
- **WHEN** the process receives SIGTERM
- **THEN** the in-flight request completes with its normal response
- **AND** subsequent `/health/ready` probes return 503 immediately

#### Scenario: Engine and Redis are released on API shutdown

- **GIVEN** a running API process
- **WHEN** the lifespan finalizer runs
- **THEN** `engine.dispose()` is invoked AND `redis.close()` is invoked
- **AND** Postgres server-side stats show the connections returned to idle within the grace window

#### Scenario: A slow finalizer step does not block the others

- **GIVEN** Redis is unreachable at shutdown time
- **WHEN** the lifespan finalizer runs
- **THEN** the Redis-close attempt logs a warning and proceeds
- **AND** `engine.dispose()` and `provider.shutdown()` still run

#### Scenario: SIGTERM during an in-flight request lets that request finish

- **GIVEN** the API is serving a request whose handler is mid-execution
- **WHEN** the process receives SIGTERM
- **THEN** uvicorn stops accepting new connections immediately
- **AND** the in-flight handler runs to completion within `APP_SHUTDOWN_TIMEOUT_SECONDS`
- **AND** the response is delivered to the client before the process exits

#### Scenario: Shutdown timeout exceeded forces termination

- **GIVEN** an in-flight request whose handler is hung beyond `APP_SHUTDOWN_TIMEOUT_SECONDS`
- **WHEN** SIGTERM is delivered and the grace window elapses
- **THEN** uvicorn cancels the remaining request task and the lifespan finalizer still runs
- **AND** `engine.dispose()`, `redis.close()`, and `provider.shutdown()` are still attempted
- **AND** the process exits before the K8s `terminationGracePeriodSeconds: 35` SIGKILL deadline

#### Scenario: Worker drain is deferred with the runtime

- **WHEN** the codebase is loaded
- **THEN** `src/worker.py` defines no `arq` `on_shutdown` hook and imports no `arq` symbol
- **AND** the engine-dispose / Redis-close / tracing-flush helpers remain callable so the future job runtime can re-bind them

### Requirement: Dockerfile exposes a dedicated worker stage

The `Dockerfile` SHALL define a dedicated worker build stage that inherits the hardened runtime base (digest-pinned base image, UID/GID 10001, tini entrypoint); only `CMD` (and optionally `HEALTHCHECK`) SHALL differ from the API runtime stage. A `Makefile` target `docker-build-worker` SHALL invoke `docker build --target runtime-worker --tag worker:latest .`. `docs/operations.md` SHALL document the two-image build pattern (API target vs worker target). The stage's `CMD` SHALL run `python -m worker`, which (until the production job runtime is added at a later roadmap step) builds the scaffold and exits non-zero with a clear "no job runtime wired" message. The stage SHALL NOT be deleted: a later roadmap step revives it for the AWS SQS + Lambda runtime.

#### Scenario: Worker image runs the scaffold and exits honestly

- **GIVEN** an image built with `--target runtime-worker`
- **WHEN** the container starts
- **THEN** the process invokes `python -m worker`, which builds the composition scaffold and exits with a non-zero status and a "no job runtime wired" message (the runtime arrives at a later roadmap step)
- **AND** the process does NOT invoke uvicorn
- **AND** the process imports no `arq` symbol

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
