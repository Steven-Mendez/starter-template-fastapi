## Context

Account lifecycle and blob lifecycle have been independent. They need to be coupled — deactivation/erasure should reclaim storage.

## Decisions

- **Async via outbox + `JobQueuePort`, never inline.** Both `DeactivateUser` and `EraseUser` enqueue the `delete_user_assets` job. Rationale: per CLAUDE.md, deferred and IO-heavy work uses the `background_jobs` feature; running blob deletion inside the HTTP request would block the response, hold the deactivation transaction open across S3 calls, and lose the worker's retry/backoff. The outbox guarantees the enqueue commits atomically with the deactivation.
- **Per-user prefix convention** as the default discovery mechanism: cheap to implement against any blob backend.
- **Rejected**: a synchronous call inside `DeactivateUser`. Couples HTTP latency to the storage backend, and a partial failure leaves the user already deactivated with no retry path.

## Non-goals

- **Not a backfill / reconciliation tool.** We do not scan existing soft-deleted users to clean up their orphaned blobs. Operators can opt into a one-shot reconciliation script in a follow-up.
- **Not multi-backend fan-out.** The default adapter walks a single `FileStoragePort`. If a future feature uses a different blob store, it ships its own cleanup adapter; we do not aggregate across backends in this change.
- **Not asset cleanup for non-user-owned resources.** Files attached to organizations, teams, or shared resources are out of scope; their lifecycle stays with the owning feature.

## Risks / Trade-offs

- **Risk**: a feature that doesn't follow the prefix convention has orphan blobs we won't catch. Mitigation: documented; future per-feature implementations can declare their own cleanup adapter.

## Migration

Single PR. Rollback safely (no schema changes).
