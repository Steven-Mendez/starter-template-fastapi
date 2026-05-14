## Why

`DeactivateUser` (`src/features/users/application/use_cases/deactivate_user.py:23-27`) only flips `is_active=False`. The user row, email, profile fields, and audit-event metadata (`family_id`, `ip_address`, `user_agent`) stay forever. There is no documented data-export endpoint and no hard-delete / scrub path. GDPR Art. 15 (right of access) and Art. 17 (right to erasure) cannot be honored without bespoke SQL — and Art. 17 explicitly grants the right to the **data subject**, so a self-erase path is required, not optional.

## What Changes

- Add `EraseUser` use case (`src/features/users/application/use_cases/erase_user.py`, new) that scrubs PII in one transaction:
  - Replace `users.email` with `erased+<uuid>@erased.invalid`, null profile fields, set `is_active=false`, `is_erased=true`.
  - `UPDATE auth_audit_events SET ip_address = NULL, user_agent = NULL, event_metadata = event_metadata - 'family_id' - 'ip_address' - 'user_agent' WHERE user_id = :uid`.
  - Delete `credentials`, `refresh_tokens`, `auth_internal_tokens`.
  - Record a final audit event `user.erased` (no PII).
  - Invoke `UserAssetsCleanupPort` (from `clean-user-assets-on-deactivate`) to purge file-storage blobs.
- Erasure is **deferred via `JobQueuePort`**: the route enqueues an `erase_user` job and returns `202 Accepted` with a job id. Rationale: the transaction can be slow (multi-table scrub + S3 deletes); 202 is the right shape for any handler that takes meaningful wall-clock time.
- **Self-erase is supported** per GDPR Art. 17. Two trigger routes:
  - `DELETE /me/erase` — self-service; the request body MUST include the user's current password for re-auth (defense in depth against a stolen session token).
  - `POST /admin/users/{user_id}/erase` — admin path (gated by `system:main#admin`).
- Add `ExportUserData` use case (`src/features/users/application/use_cases/export_user_data.py`, new). Export is **synchronous**: it serializes the user row + profile + audit events + file metadata to JSON, writes the blob to `FileStoragePort`, and returns a signed URL. For typical users the blob is small (<1 MB) so synchronous is fine; if profiling shows it isn't, swap to a job + the same signed-URL pattern.
- Export is admin-only AND self-service: `GET /me/export` (self) and `GET /admin/users/{user_id}/export` (admin).
- `UserPort.get_by_email` MUST return `None` for `is_erased=true` rows.
- Document the legal context, the PII column inventory, and the runbook in `docs/operations.md`.

**Capabilities — Modified**: `project-layout` (cross-cutting compliance), touches `authentication` + `users`.

## Impact

- **Code**:
  - `src/features/users/application/use_cases/erase_user.py` (new).
  - `src/features/users/application/use_cases/export_user_data.py` (new).
  - `src/features/users/adapters/inbound/http/me.py` (new `DELETE /me/erase`, `GET /me/export` routes).
  - `src/features/users/adapters/inbound/http/admin.py` (new `POST /admin/users/{user_id}/erase`, `GET /admin/users/{user_id}/export` routes).
  - `src/features/users/adapters/outbound/persistence/sqlmodel/models.py` (adds `is_erased BOOLEAN NOT NULL DEFAULT false`).
  - `src/features/users/adapters/outbound/persistence/sqlmodel/repository.py` (filters `is_erased` in `get_by_email`; adds scrub methods).
  - `src/features/background_jobs/composition/jobs.py` and `src/worker.py` (register the `erase_user` handler).
  - `docs/operations.md` (new "GDPR / data subject rights" section + PII column inventory).
- **Migrations**: one new column on `users` (`is_erased`); reversible — its downgrade can safely drop the column.
- **Production**: GDPR-compliant erasure + export flows ready.

## Depends on / Conflicts with

- **Depends on**: `clean-user-assets-on-deactivate` (provides `UserAssetsCleanupPort` invoked from `EraseUser`); `harden-auth-defense-in-depth` (re-auth helper for `DELETE /me/erase`); `document-one-way-migration-policy` (migration follows the policy — though this one is reversible).
- **Conflicts with (touch the same files)**: `clear-refresh-cookie-on-self-deactivate` and `clean-user-assets-on-deactivate` (all three touch `DeactivateUser` and `me.py`); `improve-db-performance` (shares `users` model); `redact-pii-and-tokens-in-logs` (PII inventory is shared).
