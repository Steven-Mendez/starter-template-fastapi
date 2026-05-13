## Why

`SQLModelAuthorizationAdapter.write_relationships` (`src/features/authorization/adapters/outbound/sqlmodel/adapter.py`, post-rename — formerly `repository.py:202-228`) commits the relationship tuples in `_write_session_scope` and **then** calls `self._user_authz_version.bump(user_id)` — which opens its own write session. The two writes are not atomic:

- If the bump write fails (transient DB error, dropped connection), the grant lands but no version invalidation is recorded. The principal cache continues serving the stale `authz_version` until the next reset of cache state, which on the in-process variant means up to `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS` per worker. On the engine path the use case never even calls `principal_cache.invalidate_user(...)`, so multi-worker deployments can hold a stale principal indefinitely.
- The inverse is also possible: a bug or race that causes the bump to win while the grant rolls back grants a privilege the underlying tuple does not have.

The session-scoped adapter (`SessionSQLModelAuthorizationAdapter`) already does this correctly because the caller's UoW owns the transaction. The engine-owning adapter is the only path with the gap, and it is used by `BootstrapSystemAdmin` and any future use case that grants/revokes outside a feature transaction.

## What Changes

- Inside `SQLModelAuthorizationAdapter.write_relationships` and `.delete_relationships`, the `_write_session_scope` MUST also call `self._user_authz_version.bump(...)` for every affected subject `user:*`, using the *same* session. The bump becomes part of the same `COMMIT`.
- Refactor `SQLModelUserAuthzVersionAdapter.bump` to expose a session-aware variant (or a `bump_in_session(session, user_id)` helper) the authz adapter can call without re-opening a new session.
- Wire `PrincipalCachePort.invalidate_user(...)` into every authorization-mutation use case (`BootstrapSystemAdmin`, future feature use cases that grant/revoke) so the cache is dropped on commit. The session-scoped path already inherits this via the surrounding UoW; the engine path is what's missing.
- Add a `SQLModelAuthorizationAdapter`-level invariant test: "after `write_relationships(...)`, both the tuple AND the bumped `authz_version` row are visible from a separate connection, OR neither is."

**Capabilities — Modified**
- `authorization`: tightens the grant/revoke requirement to mandate same-transaction version bump.

**Capabilities — New**
- None.

## Impact

- **Code paths edited**:
  - `src/features/authorization/adapters/outbound/sqlmodel/adapter.py` (post-rename — see "Depends on")
  - `src/features/authorization/application/ports/outbound/user_authz_version_port.py`
  - `src/features/users/adapters/outbound/authz_version/sqlmodel.py`
  - `src/features/authorization/application/use_cases/bootstrap_system_admin.py`
  - `docs/architecture.md`
- **Migrations**: none.
- **Production**: closes a window where role/permission changes did not invalidate cached principals.
- **Tests**: integration test with a forced failure on the bump path (e.g. patch `UserAuthzVersionPort.bump_in_session` to raise) → assert the relationship row is also absent.
- **Performance**: one fewer transaction commit per grant; one fewer pool checkout per revoke. Net positive.

## Depends on

- `rename-authz-adapter-files` — the engine-owning adapter file is renamed from `repository.py` to `adapter.py` in that change. All file paths in this change reference the post-rename path.

## Conflicts with

- `fix-bootstrap-admin-escalation` (same cluster) — both edit `BootstrapSystemAdmin`. Coordinate ordering so cache-invalidation wiring composes cleanly with the new `CredentialVerifierPort` branching.
- `improve-db-performance` (infra-deploy cluster) — same `adapter.py` edited for `lookup_subjects` limit; rebase ordering owned by that cluster.
