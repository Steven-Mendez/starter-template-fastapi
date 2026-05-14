## 1. Connection-pool defaults

- [x] 1.1 In `src/app_platform/config/settings.py` (lines 81-82), raise `db_pool_size` default to 20 and `db_max_overflow` default to 30. (`DatabaseSettings` in `sub_settings.py` is a projection — it reads these defaults; no edit there.)
- [x] 1.2 Update `docs/operations.md` Pool sizing section: document the AnyIO threadpool size, the formula (`pool_size + max_overflow >= threadpool_workers + headroom`), and how to tune via `APP_DB_POOL_SIZE` / `APP_DB_MAX_OVERFLOW`.
- [x] 1.3 Unit test: assert the default `DatabaseSettings.from_app_settings(AppSettings())` gives `pool_size=20`, `max_overflow=30`.

## 2. `users.created_at` index + keyset pagination

- [x] 2.1 Add an Alembic migration creating `ix_users_created_at` on `users(created_at, id)` using the new `_create_index_concurrently(...)` helper from task 6.
- [x] 2.2 Update `UserTable` (`features/users/adapters/outbound/persistence/sqlmodel/models.py`) to declare the index for `--autogenerate` consistency.
- [x] 2.3 Refactor `SQLModelUserRepository.list_paginated` to accept a cursor `(created_at, id)` tuple instead of an `offset`. Query: `WHERE (created_at, id) > (:c, :i) ORDER BY created_at, id LIMIT :limit`.
- [x] 2.4 Update `GET /admin/users` route signature: accept `?cursor=<base64>` and return `next_cursor` (base64-encoded `(created_at, id)`) in the response body. Document the cursor format in `docs/api.md`.
- [x] 2.5 Tests: cursor round-trip, no duplicates across pages, no missing rows when a new user is inserted between page fetches (stable iteration).

## 3. Admin audit-log cursor

- [x] 3.1 Add a `before: str | None` (base64-encoded `(created_at, id)`) query parameter to `GET /admin/audit-log`. (Deviation from the original task wording: the audit-event `id` is a UUID, not a bigserial, so the cursor carries `(created_at, id)` like the users endpoint. The spec delta and docs reflect this.)
- [x] 3.2 Update the repository method: `WHERE (:before IS NULL OR (created_at, id) < (:before_created_at, :before_id)) ORDER BY created_at DESC, id DESC LIMIT :limit`.
- [x] 3.3 Return the tail `(created_at, id)` of the page as `next_before` so the caller can paginate backwards through history.
- [x] 3.4 Tests: forward pagination across a populated table; round-trip walks the full history without gaps or duplicates.

## 4. `lookup_subjects` limit

- [x] 4.1 Add `limit: int | None = None` to `AuthorizationPort.lookup_subjects(...)`. The port enforces a hard cap of `LOOKUP_MAX_LIMIT=1000` (defined in `authorization/application/ports/authorization_port.py`). The shared constant also raises the existing `lookup_resources` cap from 500 → 1000; the existing unit test was updated to assert against the constant.
- [x] 4.2 Implement the cap in `SQLModelAuthorizationAdapter.lookup_subjects` and `SpiceDBAuthorizationAdapter.lookup_subjects` (the SpiceDB stub).
- [x] 4.3 Update any callers (none in tree today; future feature use cases will pass `limit` explicitly).
- [x] 4.4 Unit test: requesting `limit=10*LOOKUP_MAX_LIMIT` clamps to the cap; the default (no `limit`) also applies the cap.

## 5. boto3 pool sizing

- [x] 5.1 In `features/file_storage/adapters/outbound/s3/adapter.py`, replace `boto3.client("s3", region_name=...)` with `boto3.client("s3", region_name=..., config=botocore.config.Config(max_pool_connections=50, retries={"mode": "standard"}))`.
- [x] 5.2 Add a unit test that the constructed client's `meta.config.max_pool_connections` is ≥ 50.

## 6. CONCURRENTLY helper for future migrations

- [x] 6.1 Add `alembic/migration_helpers.py` exposing `create_index_concurrently(name, table, columns, where=None, unique=False)` that calls `op.execute("CREATE INDEX CONCURRENTLY ...")` inside `with op.get_context().autocommit_block():`, plus the matching `drop_index_concurrently(...)`.
- [x] 6.2 Document the rule in `docs/architecture.md`: "Migrations that touch tables expected to hold production data MUST use the concurrently helpers for index changes."
- [x] 6.3 Use the helper for the new `ix_users_created_at` migration (task 2.1).
- [x] 6.4 Add a checklist note to `CLAUDE.md` reminding contributors of the convention. (Pyproject linter rule deferred — autogenerate emits plain `op.create_index` so a lint would fight Alembic.)

## 7. Wrap-up

- [ ] 7.1 `make ci` green. (Pending — see runtime validation in the implementer report.)
- [ ] 7.2 Manual: load-test `GET /admin/users` with the keyset cursor over a 100k-row seeded users table; confirm constant page-time vs the previous offset implementation. (Skipped per implementer instructions — would require a deployed environment.)
