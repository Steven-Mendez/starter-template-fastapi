## ADDED Requirements

### Requirement: Application exposes a readiness probe distinct from liveness

The application SHALL expose `GET /health/ready`. The probe SHALL:

- Check PostgreSQL with `SELECT 1` against the engine.
- Check Redis with `PING` when `APP_AUTH_REDIS_URL` (or `APP_JOBS_REDIS_URL`) is configured.
- Check S3 with `head_bucket` when `APP_STORAGE_ENABLED=true` and `APP_STORAGE_BACKEND=s3`.

Each dependency probe SHALL be bounded by `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS` (default 1.0). Probes SHALL run in parallel so total latency is the worst single-dependency latency, not the sum.

The probe SHALL return:

- `200 {"status":"ok","deps":{...}}` when the FastAPI lifespan has completed sealing AND every configured dependency responds within its timeout.
- `503 {"status":"starting"}` while the lifespan has not yet completed sealing.
- `503 {"status":"fail","deps":{"<name>":"fail","reason":"..."}, ...}` with `Retry-After: 1` when any configured dependency times out or raises.

`GET /health/live` SHALL remain a process-only check returning 200 unconditionally once the process is accepting connections.

#### Scenario: Ready when all configured dependencies respond

- **GIVEN** a fully started process whose DB and Redis are reachable
- **WHEN** `GET /health/ready` is called
- **THEN** the response is 200 with `{"status":"ok","deps":{"db":"ok","redis":"ok"}}`

#### Scenario: Not ready when DB probe times out

- **GIVEN** the DB connection is broken
- **WHEN** `GET /health/ready` is called
- **THEN** the response is 503
- **AND** the body names `db` as the failing dependency
- **AND** the response carries `Retry-After: 1`

#### Scenario: Not ready during startup

- **GIVEN** the FastAPI lifespan has not yet completed sealing
- **WHEN** `GET /health/ready` is called
- **THEN** the response is 503 with body `{"status":"starting"}`

#### Scenario: Liveness is unaffected by dependency failure

- **GIVEN** Postgres is unreachable
- **WHEN** `GET /health/live` is called
- **THEN** the response is 200

#### Scenario: Redis configured but unreachable

- **GIVEN** `APP_AUTH_REDIS_URL` is set and Redis `PING` raises `ConnectionError`
- **WHEN** `GET /health/ready` is called
- **THEN** the response is 503
- **AND** the body names `redis` as the failing dependency with a non-empty `reason`
- **AND** the response carries `Retry-After: 1`

#### Scenario: Dependency probe exceeds timeout

- **GIVEN** `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS=0.5` and a DB probe that sleeps 2 seconds
- **WHEN** `GET /health/ready` is called
- **THEN** the response is 503 within ~0.5 s (probes run in parallel and are bounded by `asyncio.wait_for`)
- **AND** the body names `db` as the failing dependency with a timeout `reason`

#### Scenario: Optional dependency not configured is omitted from response

- **GIVEN** neither `APP_AUTH_REDIS_URL` nor `APP_JOBS_REDIS_URL` is set and `APP_STORAGE_ENABLED=false`
- **WHEN** `GET /health/ready` is called against a healthy process
- **THEN** the response is 200 with `{"status":"ok","deps":{"db":"ok"}}`
- **AND** `deps` contains no `redis` or `s3` key
