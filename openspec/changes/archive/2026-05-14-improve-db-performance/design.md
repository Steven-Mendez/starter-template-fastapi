## Context

The template ships sensible defaults for a developer laptop but doesn't articulate how those defaults scale under load. The five issues this proposal fixes are all "fine until the database is real" — they pass every existing test and look right under low concurrency. The fix isn't a rewrite; it's tightening the defaults and changing two pagination shapes from offset-based to cursor-based, plus a small helper for future migrations.

## Goals / Non-Goals

**Goals**
- Production-default pool sizing matches the request concurrency the rest of the stack can produce.
- Admin endpoints scale to arbitrarily large tables (keyset pagination, not offset).
- `lookup_subjects` has a guard rail against unbounded result sets.
- `boto3` is configured for the concurrency FastAPI actually creates.
- A clear, reusable pattern for `CREATE INDEX CONCURRENTLY` in migrations.

**Non-Goals**
- Switching to async SQLAlchemy. The codebase intentionally runs sync repos inside FastAPI's threadpool; that's a deliberate trade for simpler debugging. Re-architecting to async is a separate proposal entirely.
- Adopting a generic `Repository[T]` base class. Out of scope; the per-feature shape stays.
- Rewriting all existing migrations to use the CONCURRENTLY helper. The helper is for new migrations; reapplying it to land-and-deployed migrations gains nothing.

## Decisions

### Decision 1: Defaults of 20 + 30 = 50, not "match the threadpool"

- **Chosen**: `pool_size=20, max_overflow=30`. Total ceiling 50 connections — comfortably above the default ~40-worker AnyIO threadpool. Each pool entry is ~10 MiB of Postgres-side memory, so 50 × 10 MiB = 500 MiB worst case per replica; acceptable.
- **Rejected**: dynamically derive from `os.cpu_count()` or AnyIO config. Too clever; harder to reason about; operators read settings, not derived math.

### Decision 2: Keyset pagination, not offset

- **Chosen**: `(created_at, id)` cursor. Stable under concurrent inserts; constant time regardless of depth; uses the new composite index efficiently.
- **Rejected**: offset pagination with a hard cap. Avoids the deep-page perf hit but doesn't let admins reach old records.
- **Rejected**: page-token only (e.g. `next_page=42`). The cursor *is* the token; opaque base64 of `(created_at, id)` keeps the API surface tight.

### Decision 3: Audit log uses `id`-only cursor, not `(created_at, id)`

- **Chosen**: audit events are append-only and `id` is a monotonic BIGSERIAL; using `id` alone is correct AND simpler. The user-list case needs `created_at` because `users.id` is a UUIDv7 (or UUIDv4) — not monotonic by insert order.
- **Rejected**: uniform `(timestamp, id)` cursor everywhere. Looks consistent; loses the audit-table simplification.

### Decision 4: `lookup_subjects` cap at 1000, port-enforced

- **Chosen**: the port itself clamps. Adapters that ignore the parameter aren't a footgun; the use case sees a stable contract.
- **Rejected**: pagination on `lookup_subjects`. The use cases that need this aren't yet in tree; we add the cap now and pagination later if a real consumer needs it.

### Decision 5: `botocore.config.Config(max_pool_connections=50)`

- **Chosen**: 50 matches our DB pool ceiling — both are sized to the same concurrency budget. `retries={"mode": "standard"}` enables botocore's modern retry strategy (cumulative backoff) at no cost.
- **Rejected**: tune per-adapter via env var. Premature; can be added when an operator hits a wall.

### Decision 6: CONCURRENTLY helper, not policy + linter

- **Chosen**: a one-function helper that future migrations explicitly use. Reviewer-visible at the call site.
- **Rejected**: an automated check that every migration uses the helper. Hard to write reliably (autogenerate produces `op.create_index` by default; we'd be fighting Alembic) and not worth the maintenance.

## Risks / Trade-offs

- **Risk**: keyset cursors require clients to round-trip `next_cursor` verbatim. Clients that hand-rolled `?page=2` style URLs break. Mitigation: the response schema change is additive and documented in `docs/api.md`; no in-tree consumer relies on offset pagination.
- **Risk**: raising `max_overflow` to 30 means under sustained overload the DB sees up to 50 concurrent connections per replica, potentially hitting Postgres's `max_connections`. Mitigation: docs explain the formula and the operator-side limits (`max_connections`, PgBouncer if pooling externally).
- **Trade-off**: the `boto3` change is largely invisible until concurrency rises; the cost is one extra parameter at construction time.

## Depends on

- `rename-authz-adapter-files` — renames `src/features/authorization/adapters/outbound/sqlmodel/repository.py` → `adapter.py`. This change must land first to avoid a brutal rename-vs-edit diff conflict on the lookup-subjects cap edit.
- `make-authz-grant-atomic` — also edits the (renamed) authorization adapter file. The cleanest order is `rename-authz-adapter-files` → `make-authz-grant-atomic` → `improve-db-performance`; each rebases on the previous.

## Conflicts with

- `src/app_platform/config/sub_settings.py` is shared with `harden-rate-limiting` and `strengthen-production-validators`. Pool fields only; no logical overlap.
- `src/features/authorization/adapters/outbound/sqlmodel/repository.py` is shared with `rename-authz-adapter-files` (file rename) and `make-authz-grant-atomic` (atomic grant). See ordering above.
- `src/features/users/adapters/outbound/persistence/sqlmodel/repository.py` is shared with `make-auth-flows-transactional`. Pagination refactor is additive on top of the new session-scoped repo.
- `src/features/users/adapters/outbound/persistence/sqlmodel/models.py` is shared with `add-gdpr-erasure-and-export` (`is_erased` column). The new `ix_users_created_at` index is additive.
- `alembic/env.py` is shared with no other change in this batch.

## Migration Plan

Single PR. Order:

1. Pool defaults (config-only).
2. CONCURRENTLY helper (new module, no users yet).
3. `ix_users_created_at` migration using the helper.
4. Keyset pagination for `/admin/users`.
5. Audit-log cursor.
6. `lookup_subjects` cap.
7. boto3 config.
8. Tests + doc updates.

Rollback: revert; the only migration is a `CREATE INDEX CONCURRENTLY` which is safe to drop.
