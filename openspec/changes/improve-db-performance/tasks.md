## 1. Connection-pool defaults

- [ ] 1.1 In `src/app_platform/config/settings.py` (lines 81-82), raise `db_pool_size` default to 20 and `db_max_overflow` default to 30. (`DatabaseSettings` in `sub_settings.py` is a projection — it reads these defaults; no edit there.)
- [ ] 1.2 Update `docs/operations.md` Pool sizing section: document the AnyIO threadpool size, the formula (`pool_size + max_overflow >= threadpool_workers + headroom`), and how to tune via `APP_DB_POOL_SIZE` / `APP_DB_MAX_OVERFLOW`.
- [ ] 1.3 Unit test: assert the default `DatabaseSettings.from_app_settings(AppSettings())` gives `pool_size=20`, `max_overflow=30`.

## 2. `users.created_at` index + keyset pagination

- [ ] 2.1 Add an Alembic migration creating `ix_users_created_at` on `users(created_at, id)` using the new `_create_index_concurrently(...)` helper from task 6.
- [ ] 2.2 Update `UserTable` (`features/users/adapters/outbound/persistence/sqlmodel/models.py`) to declare the index for `--autogenerate` consistency.
- [ ] 2.3 Refactor `SQLModelUserRepository.list_paginated` to accept a cursor `(created_at, id)` tuple instead of an `offset`. Query: `WHERE (created_at, id) > (:c, :i) ORDER BY created_at, id LIMIT :limit`.
- [ ] 2.4 Update `GET /admin/users` route signature: accept `?cursor=<base64>` and return `next_cursor` (base64-encoded `(created_at, id)`) in the response body. Document the cursor format in `docs/api.md`.
- [ ] 2.5 Tests: cursor round-trip, no duplicates across pages, no missing rows when a new user is inserted between page fetches (stable iteration).

## 3. Admin audit-log cursor

- [ ] 3.1 Add a `before_id: int | None` query parameter to `GET /admin/audit-events`.
- [ ] 3.2 Update the repository method: `WHERE (:before_id IS NULL OR id < :before_id) ORDER BY id DESC LIMIT :limit`.
- [ ] 3.3 Return the smallest `id` in the response page as `next_before_id` so the caller can paginate forward.
- [ ] 3.4 Tests: forward pagination across a populated table; round-trip walks the full history without gaps or duplicates.

## 4. `lookup_subjects` limit

- [ ] 4.1 Add `limit: int | None = None` to `AuthorizationPort.lookup_subjects(...)`. The port enforces a hard cap of `LOOKUP_MAX_LIMIT=1000` (defined in `authorization/application/__init__.py` or similar).
- [ ] 4.2 Implement the cap in `SQLModelAuthorizationAdapter.lookup_subjects` and `SpiceDBAuthorizationAdapter.lookup_subjects` (the SpiceDB stub).
- [ ] 4.3 Update any callers (none in tree today; future feature use cases will pass `limit` explicitly).
- [ ] 4.4 Unit test: requesting `limit=2000` clamps to `LOOKUP_MAX_LIMIT`.

## 5. boto3 pool sizing

- [ ] 5.1 In `features/file_storage/adapters/outbound/s3/adapter.py`, replace `boto3.client("s3", region_name=...)` with `boto3.client("s3", region_name=..., config=botocore.config.Config(max_pool_connections=50, retries={"mode": "standard"}))`.
- [ ] 5.2 Add a unit test that the constructed client's `meta.config.max_pool_connections` is ≥ 50.

## 6. CONCURRENTLY helper for future migrations

- [ ] 6.1 Add `alembic/migration_helpers.py` exposing `create_index_concurrently(name, table, columns, where=None, unique=False)` that calls `op.execute("CREATE INDEX CONCURRENTLY ...")` inside `with op.get_context().autocommit_block():`, plus the matching `drop_index_concurrently(...)`.
- [ ] 6.2 Document the rule in `docs/architecture.md`: "Migrations that touch tables expected to hold production data MUST use the concurrently helpers for index changes."
- [ ] 6.3 Use the helper for the new `ix_users_created_at` migration (task 2.1).
- [ ] 6.4 Add a quick `pyproject.toml` ruff rule or a manual checklist note in `CLAUDE.md` reminding contributors of the convention. (Not strictly automatable, but the doc + helper get most of the value.)

## 7. Wrap-up

- [ ] 7.1 `make ci` green.
- [ ] 7.2 Manual: load-test `GET /admin/users` with the keyset cursor over a 100k-row seeded users table; confirm constant page-time vs the previous offset implementation.
