## MODIFIED Requirements

### Requirement: Every multi-implementation port has a dual-binding contract suite

For every outbound port that has more than one implementation in production code, the test suite SHALL contain a single contract module whose scenarios are parametrized over every implementation. The contract MUST run against the in-memory fake AND the real adapter (gated on Docker availability for adapters that require external services).

This applies to: `OutboxPort`, `AuthorizationPort`, the rate-limit port (fixed-window AND sliding-window), `PrincipalCachePort`, `EmailPort`, `JobQueuePort`, `FileStoragePort` (already exemplary — keep).

#### Scenario: Outbox contract runs against the real adapter when Docker is available

- **GIVEN** the test suite runs with Docker available
- **WHEN** `pytest src/features/outbox/tests/contracts/` runs
- **THEN** every scenario executes once against `InMemoryOutboxAdapter` and once against `SessionSQLModelOutboxAdapter`
- **AND** both bindings pass

#### Scenario: Real-adapter binding is skipped cleanly when Docker is absent

- **GIVEN** `KANBAN_SKIP_TESTCONTAINERS=1`
- **WHEN** the same suite runs
- **THEN** the real-adapter bindings are skipped (not failed) with a clear skip reason citing the env var
- **AND** the fake bindings still run and pass

### Requirement: Fakes are strict by default

In-memory test fakes for ports whose real adapters validate input (`FakeEmailPort` ↔ registry, `FakeJobQueue` ↔ `known_jobs`) SHALL raise the same validation errors as their real counterparts. Permissive behaviour MUST be opt-in via an explicit flag on construction.

#### Scenario: Fake email port rejects unknown templates

- **GIVEN** a `FakeEmailPort` constructed with a registry containing only `"welcome"`
- **WHEN** the test calls `fake.send(to="x", template_name="missing", context={})`
- **THEN** the result is `Err(UnknownTemplateError)`

#### Scenario: Fake job queue rejects unknown job names by default

- **GIVEN** a `FakeJobQueue` constructed without `permissive=True`
- **WHEN** the test calls `fake.enqueue("nonexistent_job", {})`
- **THEN** the result is `Err(UnknownJobError)`

## ADDED Requirements

### Requirement: UserAuthzVersionPort contract asserts observable side effects

The `UserAuthzVersionPortContract` SHALL assert that `bump(user_id)` causes a subsequent `read_version(user_id)` to return a strictly greater value. A "doesn't raise" assertion alone is insufficient.

#### Scenario: Bump observably increments the version

- **GIVEN** a fresh user `u` with `read_version(u.id) == v0`
- **WHEN** `bump(u.id)` is called
- **THEN** `read_version(u.id)` returns a value strictly greater than `v0`

### Requirement: Users feature `/me` routes have e2e coverage

`src/features/users/tests/e2e/` SHALL contain TestClient-based tests covering `GET /me`, `PATCH /me`, and `DELETE /me` — happy path plus authentication-failure plus invalid-input cases.

#### Scenario: GET /me returns the authenticated user's profile

- **GIVEN** an authenticated session for user `u`
- **WHEN** the client sends `GET /me`
- **THEN** the response status is 200
- **AND** the body matches `u`'s public profile fields (no `authz_version`)

#### Scenario: PATCH /me with invalid input is rejected

- **GIVEN** an authenticated session
- **WHEN** the client sends `PATCH /me` with an invalid `email` field
- **THEN** the response status is 422
- **AND** the body is a Problem Details document naming the invalid field

#### Scenario: DELETE /me deactivates the caller

- **GIVEN** an authenticated session for user `u`
- **WHEN** the client sends `DELETE /me`
- **THEN** the response status is 204
- **AND** a subsequent `GET /me` with the same access token returns 401 (account deactivated)

### Requirement: Testcontainers skip flag is uniformly named

The skip flag used by integration `conftest.py` files SHALL be `KANBAN_SKIP_TESTCONTAINERS` (the canonical name per `CLAUDE.md`). No alias (including the historical `AUTH_SKIP_TESTCONTAINERS`) is permitted.

#### Scenario: Setting the canonical flag skips all testcontainer-dependent integration tests

- **GIVEN** `KANBAN_SKIP_TESTCONTAINERS=1`
- **WHEN** `make test-integration` runs
- **THEN** every integration test that would otherwise spin a container is skipped with a reason citing `KANBAN_SKIP_TESTCONTAINERS`
- **AND** no test errors out trying to reach a container

#### Scenario: The historical alias is gone

- **GIVEN** the codebase after this change lands
- **WHEN** `rg AUTH_SKIP_TESTCONTAINERS` runs
- **THEN** there are zero matches under `src/` and zero in documentation

### Requirement: Integration markers reflect real-backend usage

A test marked `integration` SHALL exercise the real backend (real Postgres / real Redis / real S3 via testcontainers or moto). Tests that use in-memory stubs (`fakeredis`, etc.) MUST be marked `unit` instead.

#### Scenario: fakeredis-backed test is not labeled integration

- **GIVEN** `src/features/background_jobs/tests/integration/test_arq_round_trip.py` (which uses `fakeredis`)
- **WHEN** the test marker is inspected after this change lands
- **THEN** it is marked `unit`, not `integration` (and the file moves under a `tests/unit/` path if marker convention requires)
- **AND** a sibling `test_arq_redis_round_trip.py` exists with the `integration` marker against real Redis via `testcontainers`
