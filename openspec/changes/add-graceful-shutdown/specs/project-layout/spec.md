## ADDED Requirements

### Requirement: Process shutdown is graceful and bounded

The API server SHALL be launched with `--timeout-graceful-shutdown` equal to `APP_SHUTDOWN_TIMEOUT_SECONDS` (default 30 s). On SIGTERM the FastAPI `lifespan` finalizer SHALL:

1. Clear the readiness flag so subsequent `/health/ready` probes return 503.
2. Drain in-flight requests up to `APP_SHUTDOWN_TIMEOUT_SECONDS` (uvicorn enforces this).
3. Dispose the SQLAlchemy engine.
4. Close the Redis client.
5. Call `provider.shutdown()` on the OTel `TracerProvider` to flush the `BatchSpanProcessor`.

Each finalizer step SHALL be wrapped in `try/except` + warn log so a slow step does not skip the others.

The arq worker SHALL implement `on_shutdown` that waits for in-flight `DispatchPending.execute` ticks and active job handlers to complete (bounded by `APP_SHUTDOWN_TIMEOUT_SECONDS`) before disposing the engine and closing Redis.

#### Scenario: SIGTERM mid-request drains before exit

- **GIVEN** an API replica with an in-flight request expected to complete in less than `APP_SHUTDOWN_TIMEOUT_SECONDS`
- **WHEN** the process receives SIGTERM
- **THEN** the in-flight request completes with its normal response
- **AND** subsequent `/health/ready` probes return 503 immediately

#### Scenario: SIGTERM mid-relay does not leave half-committed rows

- **GIVEN** a worker actively dispatching outbox rows
- **WHEN** the process receives SIGTERM
- **THEN** the in-flight row's transaction commits or rolls back cleanly before the process exits
- **AND** no row remains in an intermediate `processing` state without a corresponding lock release

#### Scenario: Engine and Redis are released on shutdown

- **GIVEN** a running API or worker process
- **WHEN** the lifespan or `on_shutdown` finalizer runs
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
