## 1. Port + adapter

- [ ] 1.1 Declare `UserAssetsCleanupPort` Protocol in `src/features/users/application/ports/user_assets_cleanup_port.py` with `delete_user_assets(user_id: UserId) -> Result[None, AssetsCleanupError]`.
- [ ] 1.2 Implement `FileStorageUserAssetsAdapter` in `src/features/users/adapters/outbound/file_storage_user_assets/adapter.py` that delegates to `FileStoragePort` using the per-user prefix `users/{user_id}/`.
- [ ] 1.3 Wire the port and adapter in `src/features/users/composition/container.py`, taking `FileStoragePort` as a dependency.

## 2. Enqueue from use cases

- [ ] 2.1 Modify `src/features/users/application/use_cases/deactivate_user.py` to enqueue a `delete_user_assets` outbox job (payload `{"user_id": ...}`) inside the same transaction that deactivates the user.
- [ ] 2.2 Modify `src/features/users/application/use_cases/erase_user.py` (from `add-gdpr-erasure-and-export`) to enqueue the same job through the same outbox path.
- [ ] 2.3 Forbid inline invocation: assert in code review and via a unit test that neither use case calls `UserAssetsCleanupPort.delete_user_assets` directly.

## 3. Job handler registration

- [ ] 3.1 Register the `delete_user_assets` handler in `src/main.py` against the `JobHandlerRegistry`. The handler resolves `UserAssetsCleanupPort` from the users container and invokes it.
- [ ] 3.2 Register the same handler in `src/worker.py` so the arq worker can run it.
- [ ] 3.3 The handler is idempotent on the user id: if `UserAssetsCleanupPort.delete_user_assets(user_id)` finds no blobs (already cleaned, or user never had any), return `Ok(None)` so the outbox row transitions to `delivered` on the first tick. Combined with `__outbox_message_id` dedup (from `fix-outbox-dispatch-idempotency`), repeated relay attempts for the same row are no-ops.

## 4. Tests

- [ ] 4.1 Integration: upload 3 blobs as user U through the local backend, deactivate U, run one relay tick + one worker tick, assert all 3 blobs are absent from the backend and the outbox row reaches `delivered` (post-`fix-outbox-dispatch-idempotency` state name).
- [ ] 4.2 Integration (moto): repeat against the moto-backed S3 adapter.
- [ ] 4.3 Unit: `DeactivateUser` writes an outbox row with name `delete_user_assets` and payload `{"user_id": ...}` inside the deactivation transaction.

## 5. Docs

- [ ] 5.1 Document the per-user prefix convention and the enqueue-not-inline rule in `docs/file-storage.md`.
- [ ] 5.2 Run `make ci` and confirm it is green.
