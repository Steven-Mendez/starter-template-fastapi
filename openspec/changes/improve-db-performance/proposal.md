## Why

Five independent DB / I/O patterns make the template look fine on a developer laptop and brittle under any real concurrency:

1. **Connection pool is sized below FastAPI's threadpool.** Defaults: `pool_size=5`, `max_overflow=10` (`src/app_platform/config/settings.py:81-82`) → 15 connection ceiling. FastAPI's AnyIO threadpool is ~40 workers; every sync route holds a connection. Under load you get `QueuePool overflow timeout` and request hangs.
2. **Repository session-per-query.** `users` and `authentication` adapters open a fresh `Session(self.engine)` on every method (`features/users/.../repository.py` and `features/authentication/.../repository.py`). A single `LoginUser` is ~5 pool checkouts + 5 commits, serialised round trips.
3. **Admin endpoints have no real pagination.** `GET /admin/users` uses `ORDER BY created_at OFFSET ... LIMIT ...` with no index on `created_at` — full sort + scan, O(N) on deep offsets. `GET /admin/audit-events` has a `limit` cap (500) but no cursor — older events become unreachable.
4. **`lookup_subjects` is unbounded.** `authorization/.../sqlmodel/repository.py:160-188` has no `limit` parameter and no SQL `LIMIT`. A popular resource streams the whole subject list into memory.
5. **`boto3.client("s3", ...)` is constructed with default `botocore` config.** Default `max_pool_connections=10`, well below FastAPI's threadpool. Concurrent uploads queue on the HTTP pool.

Plus a cross-cutting tooling gap: every existing Alembic migration runs `op.create_index(...)` plainly, taking `ACCESS EXCLUSIVE`. Fine on dev DBs, dangerous on a populated prod table.

## What Changes

- Raise default pool sizing to `pool_size=20, max_overflow=30` (50 connections total). Document the relationship to AnyIO's threadpool in `docs/operations.md`.
- Add `sa.Index("ix_users_created_at", "created_at")` and migrate `ListUsers` admin endpoint to **keyset pagination** (`WHERE (created_at, id) > (:c, :i) ORDER BY created_at, id LIMIT N`) with a `next_cursor` returned in the response.
- Add a `before_id` cursor parameter to the admin audit-log endpoint; query becomes `WHERE id < :before_id ORDER BY id DESC LIMIT :limit`.
- Add a `limit` parameter (capped at `LOOKUP_MAX_LIMIT=1000`) to `AuthorizationPort.lookup_subjects(...)` and enforce the cap in the SQLModel adapter.
- Configure boto3 with `botocore.config.Config(max_pool_connections=50, retries={"mode": "standard"})`.
- Add a `_create_index_concurrently(...)` helper in `alembic/env.py` (or as a util module) that wraps `op.execute` inside `with op.get_context().autocommit_block():`. Existing migrations stay as-is; new migrations on populated tables MUST use the helper. Document the rule in `docs/architecture.md`.

**Capabilities — Modified**
- `project-layout`: tightens cross-cutting performance/scaling defaults. (Touches `authentication`, `authorization`, `file-storage`, but the changes are not feature-specific — they're platform defaults that every feature inherits.)

**Capabilities — New**
- None.

## Impact

- **Code**: `app_platform/config/sub_settings.py`, `users/adapters/outbound/persistence/sqlmodel/`, `authentication/adapters/inbound/http/admin.py`, `authorization/adapters/outbound/sqlmodel/repository.py`, `file_storage/adapters/outbound/s3/adapter.py`, `alembic/env.py`.
- **Migrations**: one Alembic revision adding `ix_users_created_at` via the new CONCURRENTLY helper.
- **Production**: meaningful latency + throughput improvement; existing API responses gain a `next_cursor` field on paginated endpoints (additive, backwards-compatible).
- **Tests**: pagination correctness (cursor round-trip, no duplicates across pages, no missing rows under concurrent inserts), boto3 config presence, pool-sizing default sanity test.

## Conflicts with

- `rename-authz-adapter-files` (authorization cluster) — edits the same authorization adapter file (`repository.py`, renamed to `adapter.py` there). Rebase after the rename lands; update the path in the impact list accordingly.
- `make-authz-grant-atomic` (authorization cluster) — also edits the engine-owning authorization adapter for atomic version-bump. Coordinate ordering with the authorization-cluster owner.
