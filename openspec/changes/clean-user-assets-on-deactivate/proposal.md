## Why

`DELETE /me` is "soft delete" only. `FileStoragePort` has no awareness of ownership and the users feature never calls `FileStoragePort.delete`. Any blobs the user uploaded become orphans — a real cost in S3 and a privacy/GDPR concern.

## What Changes

- Introduce a `UserAssetsCleanupPort` Protocol in `features/users/application/ports/`. Method: `delete_user_assets(user_id) -> Result[None, Error]`.
- A `FileStorageUserAssetsAdapter` implements the port by walking ReBAC tuples (subject=user, relation=`owner`, resource=file:*) and deleting each blob — or by querying a user-to-asset index table maintained by feature code.
- `DeactivateUser` enqueues the `delete_user_assets` job through the outbox (writing the outbox row inside the deactivation transaction); the worker handler resolves `UserAssetsCleanupPort` and invokes it.
- `EraseUser` (from `add-gdpr-erasure-and-export`) enqueues the same job through the same path — never inline — so transient storage failures retry under the worker's existing backoff.

**Resolved decision (was open):** asset cleanup runs as a background job through `JobQueuePort` / the outbox relay, never synchronously in `DeactivateUser` or `EraseUser`. Rationale: per CLAUDE.md, deferred or IO-heavy work uses the `background_jobs` feature; blob deletion can be slow (S3 list+delete in batches), can fail transiently, and must not block the HTTP path or hold the deactivation transaction open.

**Capabilities — Modified**: `project-layout` (because it touches users + file-storage cohesively).

## Depends on

- `clean-architecture-seams` — `DeactivateUser` enqueues through `OutboxUnitOfWorkPort` introduced there. If this change lands first, it MAY use the interim `SessionScopedOutboxFactory` and rebase later.
- `fix-outbox-dispatch-idempotency` (soft) — the new job benefits from the dedup table once that change lands; not a blocker.

## Conflicts with

- `clear-refresh-cookie-on-self-deactivate` — also edits `DeactivateUser` and `src/features/users/adapters/inbound/http/me.py`. Whichever lands second rebases the use-case signature.
- `add-gdpr-erasure-and-export` — introduces `EraseUser`, which this change references. If `add-gdpr-erasure-and-export` lands second, it adopts the same enqueue path; if it lands first, this change adds the enqueue to `EraseUser` in addition to `DeactivateUser`.

## Impact

- **Code (new)**: `src/features/users/application/ports/user_assets_cleanup_port.py`, `src/features/users/adapters/outbound/file_storage_user_assets/adapter.py` (default `FileStorageUserAssetsAdapter`).
- **Code (modified)**: `src/features/users/application/use_cases/deactivate_user.py` (enqueue after commit), `src/features/users/composition/container.py` (wire port + adapter), `src/main.py` (register `delete_user_assets` handler in `JobHandlerRegistry`), `src/worker.py` (register the same handler), `docs/file-storage.md`.
- **Tests**: integration — upload N blobs as user U, deactivate U, run relay + worker tick → assert blobs absent (local backend and moto-backed S3).
- **Production**: prevents orphaned blobs; HTTP path for `DELETE /me` stays fast; failure of the storage backend does not roll back the user's deactivation.
