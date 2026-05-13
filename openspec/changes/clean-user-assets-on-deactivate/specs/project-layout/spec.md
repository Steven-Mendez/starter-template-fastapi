## ADDED Requirements

### Requirement: User deactivation and erasure trigger asset cleanup asynchronously

`DeactivateUser` and `EraseUser` SHALL enqueue a `delete_user_assets` job through the outbox in the same transaction that mutates the user. They MUST NOT invoke `UserAssetsCleanupPort.delete_user_assets` synchronously on the HTTP request path. A worker handler registered in both `src/main.py` and `src/worker.py` SHALL resolve `UserAssetsCleanupPort` and invoke `delete_user_assets(user_id)`. The default `FileStorageUserAssetsAdapter` SHALL delete every blob under the user's per-user prefix on `FileStoragePort`.

#### Scenario: Deactivation enqueues asset cleanup atomically

- **GIVEN** user U has uploaded 3 blobs to the local file-storage backend
- **WHEN** U calls `DELETE /me`
- **THEN** the same database transaction that marks U deactivated writes one outbox row with name `delete_user_assets` and payload `{"user_id": "<U>"}`
- **AND** the HTTP response returns before any blob is deleted

#### Scenario: Worker handler deletes the user's blobs

- **GIVEN** the outbox row from the preceding scenario
- **WHEN** the outbox relay dispatches the job and the worker runs the handler
- **THEN** all 3 blobs are absent from the backend
- **AND** the outbox row's status transitions to `delivered` (per the row-state machine landed by `fix-outbox-dispatch-idempotency`)

#### Scenario: Use cases do not call the port inline

- **GIVEN** the modules `deactivate_user.py` and `erase_user.py`
- **WHEN** a static-import test scans them
- **THEN** neither module references `UserAssetsCleanupPort.delete_user_assets` as a direct call site; the only references are to the job name constant

#### Scenario: Erasure uses the same enqueue path

- **GIVEN** an admin invokes `EraseUser` for user U
- **WHEN** the use case commits
- **THEN** a `delete_user_assets` outbox row exists for U, identical in shape to the deactivation case

#### Scenario: Cleanup adapter failure does not roll back the deactivation

- **GIVEN** user U is deactivated and a `delete_user_assets` outbox row is dispatched
- **WHEN** `FileStoragePort.delete` raises a transient error on the first attempt
- **THEN** U remains deactivated (the user-row mutation already committed)
- **AND** the outbox row stays in a retryable state and the next worker tick re-attempts the cleanup under the existing backoff
- **AND** the handler completes idempotently once the backend recovers (no duplicate deletes, no resurrection of the deactivation)

#### Scenario: User with no uploaded blobs is a no-op

- **GIVEN** user U has never uploaded any file under the `users/{user_id}/` prefix
- **WHEN** U deactivates and the `delete_user_assets` handler runs
- **THEN** the handler returns `Ok(None)` without raising
- **AND** the outbox row transitions to `delivered` on the first tick (no retry loop on an empty prefix)
