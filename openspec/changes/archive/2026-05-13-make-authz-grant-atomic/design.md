## Context

ReBAC reads pass through a per-user `authz_version` so the principal cache can detect staleness on every miss-then-fill. Writes — `write_relationships` and `delete_relationships` — must bump the version any time they mutate something that could change a `check` outcome. The session-scoped authz adapter already does this correctly because the caller's UoW owns the session and both writes commit together. The engine-owning adapter splits the writes across two sessions, so any deploy that grants/revokes via the engine path (today: bootstrap; tomorrow: any admin endpoint without a feature UoW) has a small but real consistency window.

Principal-cache invalidation is the third actor: the bumped version stops stale cache *entries* from being trusted on future misses, but an entry that's still inside its TTL window will keep being served. The use case is supposed to drop those entries on grant/revoke; today only the session-scoped path inherits the invalidation from its UoW commit hooks. The engine path forgets.

## Goals / Non-Goals

**Goals**
- Atomicity: a relationship row and the matching `authz_version` bump commit together or neither commits.
- Same observability whether the caller writes through the engine or through a session UoW.
- Cache invalidation is fired from the use-case layer on commit, on both paths.

**Non-Goals**
- Refactoring the principal-cache strategy itself (TTL vs revocation list vs Redis-pub/sub). Covered in `harden-rate-limiting` (distributed-state gating) and `strengthen-test-contracts` (cache contract).
- Adding 2PC across Redis (cache) and Postgres (DB). Cache invalidation is best-effort; correctness comes from the DB-side `authz_version` bump being read on every miss.

## Decisions

### Decision 1: `bump_in_session` on the port, not a session-aware overload

- **Chosen**: add a second method `bump_in_session(session, user_id) -> None`. Pure SQL, no commit. The existing engine-owning `bump(user_id)` is preserved as a thin wrapper for callers (tests, ad-hoc maintenance scripts) that don't have a session in hand.
- **Rejected**: making `bump` polymorphic via an optional `session: Session | None` argument. Optional session args are a smell — every caller has to remember to thread one through, and the type checker can't distinguish "engine-owning use case" from "session-scoped use case".

### Decision 2: Caller invalidates the cache, not the adapter

- **Chosen**: `PrincipalCachePort.invalidate_user(...)` is called from the use-case layer (after the adapter returns `Ok`). The use case already has the user ids and the cache instance through DI.
- **Rejected**: making the adapter call the cache. Adapters should not depend on the principal-cache port — the cache is a use-case-layer optimization, not a write-path concern, and pushing it into the adapter would mean every implementation (SQLModel, SpiceDB, future Mongo) needs the dep.

### Decision 3: One bump per affected user, deduped

- **Chosen**: `write_relationships` and `delete_relationships` may receive multiple tuples affecting the same subject. Collect affected `user:*` ids into a set; bump each exactly once per transaction.
- **Rejected**: bump per tuple. Wastes writes; nothing about correctness requires it.

## Risks / Trade-offs

- **Risk**: the new `bump_in_session` method is a port change that requires every implementor (today: just `SQLModelUserAuthzVersionAdapter`) to follow suit. Mitigation: there's only one implementor; the in-memory test fake also needs an update but it's a one-line stub.
- **Risk**: cache invalidation is best-effort (Redis blip swallows the call). Mitigation: that's already true; the DB-side bump is the durable source of truth and the cache will self-correct on the next TTL boundary.

## Migration Plan

Single PR; no schema migration.

1. Add `bump_in_session` to the port and adapter.
2. Refactor `SQLModelAuthorizationAdapter.write_relationships` and `.delete_relationships` (in `src/features/authorization/adapters/outbound/sqlmodel/adapter.py`, post-rename) to use it inside the existing session scope.
3. Add cache invalidation to `BootstrapSystemAdmin` and any other engine-path callers.
4. Tests: failure-injection integration test for atomicity; unit test for cache invalidation.

Rollback: revert; no persistence changes.

## Depends on

- `rename-authz-adapter-files` — this change edits the engine-owning authorization adapter, which is renamed from `repository.py` to `adapter.py` in that change. All file references in tasks and specs use the post-rename path.

## Conflicts with

- `fix-bootstrap-admin-escalation` (same cluster) — both edit `BootstrapSystemAdmin`. The two changes compose: this change adds `principal_cache.invalidate_user(...)` on the success path; the bootstrap-escalation change reshapes the branching with a new `CredentialVerifierPort`. Whichever lands second rebases and threads the cache invalidation through every new success path (paths `c` idempotent-noop has no cache to invalidate; paths `a` create-and-grant and `e` promote-existing both must call it).
- `improve-db-performance` (infra-deploy cluster) — same `adapter.py` edited to cap `lookup_subjects`. Coordinated by the infra-deploy cluster owner; no semantic conflict, only textual.
