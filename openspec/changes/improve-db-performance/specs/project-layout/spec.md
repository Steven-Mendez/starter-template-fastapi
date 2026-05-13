## MODIFIED Requirements

### Requirement: Default connection pool matches FastAPI threadpool concurrency

The default `DatabaseSettings` SHALL configure `pool_size=20` and `max_overflow=30` (total ceiling 50). `docs/operations.md` SHALL document the relationship between `pool_size + max_overflow` and the AnyIO threadpool size, including the formula `pool_size + max_overflow >= threadpool_workers + headroom`.

#### Scenario: Defaults sized for typical FastAPI concurrency

- **GIVEN** an unmodified `DatabaseSettings()`
- **WHEN** the settings are constructed
- **THEN** `pool_size == 20` and `max_overflow == 30`

## ADDED Requirements

### Requirement: Admin list endpoints use keyset pagination

`GET /admin/users` SHALL paginate via a `(created_at, id)` keyset cursor. The response SHALL include a `next_cursor` field (base64-encoded) when more rows are available; clients submit it as `?cursor=...` to fetch the next page. The underlying repository query MUST use `WHERE (created_at, id) > (:c, :i) ORDER BY created_at, id LIMIT :limit` against an index on `(created_at, id)`.

`GET /admin/audit-events` SHALL accept a `before_id: int | None` query parameter and return `next_before_id` in the response. The underlying query is `WHERE (:before_id IS NULL OR id < :before_id) ORDER BY id DESC LIMIT :limit`.

#### Scenario: Cursor round-trip walks every row without duplicates

- **GIVEN** 1,000 users seeded into a Postgres database
- **WHEN** a client repeatedly fetches `GET /admin/users?limit=100` and threads `next_cursor` through subsequent requests
- **THEN** exactly 1,000 distinct users are observed across the 10 pages
- **AND** the final response omits `next_cursor`

#### Scenario: Cursor pagination is stable under concurrent inserts

- **GIVEN** a paginated walk of `/admin/users` in progress
- **WHEN** a new user is inserted between page fetches
- **THEN** the walk still terminates and visits every original row exactly once

#### Scenario: Malformed cursor is rejected with 400

- **GIVEN** a client submits `GET /admin/users?cursor=not-valid-base64`
- **WHEN** the route decodes the cursor
- **THEN** the response is `400 Bad Request` (Problem Details)
- **AND** no rows are returned and no SQL is executed against the database

### Requirement: `AuthorizationPort.lookup_subjects` is bounded

`AuthorizationPort.lookup_subjects(...)` SHALL accept an optional `limit: int | None` parameter and SHALL enforce a hard cap of `LOOKUP_MAX_LIMIT=1000`. Adapters MUST honor the clamped limit in the underlying query.

#### Scenario: Limit is clamped to the hard cap

- **WHEN** a caller invokes `lookup_subjects(..., limit=5000)`
- **THEN** the adapter executes a query with `LIMIT 1000`

#### Scenario: Default (no limit passed) still applies the cap

- **WHEN** a caller invokes `lookup_subjects(...)` without passing `limit`
- **THEN** the adapter executes a query with `LIMIT 1000`
- **AND** the returned list contains at most 1000 subject ids

### Requirement: S3 adapter is configured for FastAPI concurrency

`S3FileStorageAdapter` SHALL construct its boto3 client with `botocore.config.Config(max_pool_connections=50, retries={"mode": "standard"})`.

#### Scenario: Constructed client exposes the expected pool size

- **WHEN** a test inspects the adapter's internal boto3 client
- **THEN** `client.meta.config.max_pool_connections == 50`

### Requirement: New migrations use CONCURRENTLY for index changes on populated tables

The project SHALL ship `alembic/migration_helpers.py` exposing `create_index_concurrently(...)` and `drop_index_concurrently(...)` helpers that wrap `op.execute(...)` inside `op.get_context().autocommit_block()`. The convention "use these helpers for any index change on a table expected to hold production data" SHALL be documented in `docs/architecture.md`.

#### Scenario: Helper produces a non-blocking index migration

- **GIVEN** an Alembic migration that calls `create_index_concurrently("ix_users_created_at", "users", ["created_at", "id"])`
- **WHEN** the migration is applied to a populated table
- **THEN** the SQL executed is `CREATE INDEX CONCURRENTLY ix_users_created_at ON users (created_at, id)`
- **AND** no `ACCESS EXCLUSIVE` lock is held during the build
