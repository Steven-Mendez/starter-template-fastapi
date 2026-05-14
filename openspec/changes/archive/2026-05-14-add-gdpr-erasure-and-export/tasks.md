## 1. Schema

- [x] 1.1 Add `is_erased: bool` (NOT NULL DEFAULT false) to `UserTable` in `src/features/users/adapters/outbound/persistence/sqlmodel/models.py`.
- [x] 1.2 Generate alembic migration; downgrade drops the column (reversible — no `NotImplementedError` needed).

## 2. EraseUser use case

- [x] 2.1 Create `src/features/users/application/use_cases/erase_user.py` with an `EraseUser` use case whose `execute(user_id, reason)` runs in a single transaction (uses the `OutboxUnitOfWorkPort`-aware writer pattern landed by `make-auth-flows-transactional`).
- [x] 2.1a Scrub the `users` row (verified against `src/features/users/adapters/outbound/persistence/sqlmodel/models.py`): `email` → `erased+{user_id}@erased.invalid`, `is_active` → `false`, `is_erased` → `true`, `last_login_at` → `NULL`, `authz_version` → bump. `is_verified` is preserved — boolean facts about state are not PII. The current schema has no `first_name`/`last_name` columns; the scrub list grows only when such columns are added (step 7's PII inventory makes that explicit).
- [x] 2.1b Scrub audit-event metadata: `UPDATE auth_audit_events SET event_metadata = event_metadata - 'family_id' - 'ip_address' - 'user_agent' WHERE user_id = :uid`. Verify there are no separate `ip_address`/`user_agent` columns on `auth_audit_events`; both PII keys live only inside the `event_metadata` JSONB.
- [x] 2.1c Delete the credential-bearing rows: `DELETE FROM credentials WHERE user_id = :uid`; the same for `refresh_tokens` and `auth_internal_tokens`. All three deletes run inside the same transaction as 2.1a/2.1b.
- [x] 2.1d Enqueue a `delete_user_assets` outbox row (NOT inline — the storage call may take seconds; reuses the job registered by `clean-user-assets-on-deactivate`).
- [x] 2.1e Record a `user.erased` audit event with payload `{user_id, reason: "self_request" | "admin_request"}` (no email, no IP — the event itself must not reintroduce PII).
- [x] 2.2 Filter `is_erased=true` rows out of `UserPort.get_by_email` and `get_by_id`. The latter returns `None`, which combined with the `authz_version` bump above means every cached principal entry resolves to "user not found" within the cache TTL.

## 3. Job handler

- [x] 3.1 Register an `erase_user` job handler with `JobHandlerRegistry` in both `src/main.py` and `src/worker.py`. The handler calls `EraseUser.execute(user_id)`. Idempotent.

## 4. ExportUserData use case

- [x] 4.1 Implement `src/features/users/application/use_cases/export_user_data.py`. `execute(user_id) -> Result[ExportContract, ApplicationError]` where `ExportContract` is `(download_url: str, expires_at: datetime)`.
- [x] 4.2 The use case serializes `(user row, profile, audit events for the user, file metadata)` to JSON, writes via `FileStoragePort.put(path=f"exports/{user_id}/{uuid}.json")`, and calls `FileStoragePort.signed_url(path, ttl_seconds=900)`.

## 5. HTTP routes

- [x] 5.1 `DELETE /me/erase` in `src/features/users/adapters/inbound/http/me.py`. Body: `{password: str}` (or fresh-token check for password-less accounts). On success, enqueue `erase_user` and return `202 Accepted` with `{status: "accepted", job_id, estimated_completion_seconds: 60}` and `Location: /me/erase/status/<job_id>`.
- [x] 5.2 `POST /admin/users/{user_id}/erase` in `src/features/users/adapters/inbound/http/admin.py`. Gated by `require_authorization("admin", "system:main")`. Same enqueue + 202 contract.
- [x] 5.3 `GET /me/export` in `me.py`. Returns `200 OK` with `{download_url, expires_at}`.
- [x] 5.4 `GET /admin/users/{user_id}/export` in `admin.py`. Gated by admin authz. Same response shape.

## 6. Tests

- [x] 6.1 Integration (real Postgres): erase a user → email becomes `erased+...@erased.invalid`; audit metadata has no `ip_address`/`user_agent`/`family_id`; `credentials`/`refresh_tokens`/`auth_internal_tokens` rows gone; `is_erased=true`.
- [x] 6.2 Integration: post-erasure, `UserPort.get_by_email(original_email)` returns `None`; `UserPort.get_by_id(uid)` returns `None`.
- [x] 6.3 Integration: a re-registration with the original email succeeds and produces a fresh `user_id`.
- [x] 6.4 Integration: `erase_user` is idempotent — running it twice on the same `user_id` does not raise.
- [x] 6.5 e2e: `DELETE /me/erase` with correct password → 202 with job id; with incorrect password → 401.
- [x] 6.6 e2e: `POST /admin/users/{user_id}/erase` as admin → 202; as non-admin → 403.
- [x] 6.7 e2e: `GET /me/export` returns a signed URL; fetching the URL yields a JSON document containing the user row, profile, audit events.
- [x] 6.8 PII-residue test: after erasure, no row in `users`, `auth_audit_events`, `credentials`, `refresh_tokens`, `auth_internal_tokens` contains the original email substring or the original IP.

## 7. Docs

- [x] 7.1 Add `docs/operations.md` section "GDPR / data subject rights" covering:
  - The two erasure routes and the re-auth requirement on `/me/erase`.
  - The export route shape and signed-URL TTL.
  - The PII column inventory (a literal table of columns scrubbed per row).
  - Runbook: "what to do when legal sends a written request".
- [x] 7.2 Update `CLAUDE.md` "Adding a new feature" to require updating the PII column inventory when a new user-referencing column is added.

## 8. Wrap-up

- [x] 8.1 `make ci` green.
- [x] 8.2 `make migrations-check` green (per `document-one-way-migration-policy`).
