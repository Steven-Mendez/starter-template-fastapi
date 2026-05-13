## 1. Session-aware version bump

- [ ] 1.1 Add `bump_in_session(session: Session, user_id: UUID) -> None` to `UserAuthzVersionPort` (`src/features/authorization/application/ports/outbound/user_authz_version_port.py`).
- [ ] 1.2 Implement `bump_in_session` against the supplied session (no commit) in both adapters in `src/features/users/adapters/outbound/authz_version/sqlmodel.py`.
  - [ ] 1.2.a `SQLModelUserAuthzVersionAdapter.bump_in_session` — delegates to the existing `_bump_one(session, user_id)` helper (see `src/features/users/adapters/outbound/authz_version/sqlmodel.py:25-37`).
  - [ ] 1.2.b `SessionSQLModelUserAuthzVersionAdapter.bump_in_session` — same `_bump_one` delegation; satisfies the Protocol so both adapters implement the new port method.
- [ ] 1.3 Keep the engine-owning `bump(user_id)` method on `SQLModelUserAuthzVersionAdapter` as a thin wrapper that opens its own `Session(self._engine, expire_on_commit=False)`, delegates to `bump_in_session(session, user_id)`, and commits (mirrors the existing pattern at `src/features/users/adapters/outbound/authz_version/sqlmodel.py:46-53`). Existing call sites continue to work unchanged.

## 2. Authz adapter uses the in-session bump

- [ ] 2.1 In `SQLModelAuthorizationAdapter.write_relationships` (`src/features/authorization/adapters/outbound/sqlmodel/adapter.py`, post-rename), move the `self._user_authz_version.bump(uid)` calls inside the `with self._write_session_scope() as session:` block and call `bump_in_session(session, uid)` instead. Collect affected user ids first; bump each exactly once.
- [ ] 2.2 Apply the same change in `SQLModelAuthorizationAdapter.delete_relationships`.
- [ ] 2.3 Extract a private `_bump_affected_users(session, relations)` helper so both methods share the dedup-and-bump logic.

## 3. Principal cache invalidation from use cases

- [ ] 3.1 Define a thin `PrincipalCacheInvalidatorPort` Protocol exposing only `invalidate_user(user_id: UUID) -> None`.
  - [ ] 3.1.a Create file `src/features/authorization/application/ports/outbound/principal_cache_invalidator_port.py` with the Protocol.
  - [ ] 3.1.b Export it from `src/features/authorization/application/ports/outbound/__init__.py` alongside the existing `AuditPort` / `UserRegistrarPort` exports.
  - [ ] 3.1.c Boundary check: authorization MUST NOT import `features.authentication.application.cache.PrincipalCachePort` directly — the cache implementation lives in `authentication`, the port that authorization consumes lives in authorization (mirrors the `AuditPort` pattern).
  - [ ] 3.1.d In the authentication feature, add an adapter that wraps its existing `PrincipalCache` and satisfies `PrincipalCacheInvalidatorPort` (suggested location: `src/features/authentication/adapters/outbound/principal_cache_invalidator/` mirroring the audit adapter layout — verify location against existing auth adapter conventions).
- [ ] 3.2 Update `BootstrapSystemAdmin` (`src/features/authorization/application/use_cases/bootstrap_system_admin.py`) to call the cache invalidator after a successful relationship write.
  - [ ] 3.2.a Add a 4th constructor field `_principal_cache_invalidator: PrincipalCacheInvalidatorPort` to the `@dataclass(slots=True)` (alongside `_authorization`, `_user_registrar`, `_audit` at lines 33-35).
  - [ ] 3.2.b After `self._authorization.write_relationships(...)` returns (note: `write_relationships` returns `None`, not `Result` — see `application/ports/authorization_port.py:95`), call `self._principal_cache_invalidator.invalidate_user(user_id)`.
  - [ ] 3.2.c Wrap the invalidator call in `try/except Exception as exc: _logger.warning("event=authz.cache_invalidation.failed user_id=%s reason=%r", user_id, exc)` so a Redis blip never poisons the bootstrap success.
- [ ] 3.3 Wire the new port through composition.
  - [ ] 3.3.a Update `src/features/authorization/composition/container.py` to accept the invalidator and pass it to `BootstrapSystemAdmin`.
  - [ ] 3.3.b Update `src/main.py` to construct the auth-side adapter (after the authentication container exists, before the authorization container is built) and pass it into the authorization container.
  - [ ] 3.3.c Confirm the audit event `authz.bootstrap_admin_assigned` (`bootstrap_system_admin.py:60`) is unchanged.
- [ ] 3.4 Audit `src/features/authorization/application/use_cases/` for any other engine-path grant/revoke calls and add the same invalidation pattern.
- [ ] 3.5 Document the invariant in `docs/architecture.md`: "callers of `AuthorizationPort.write_relationships` / `.delete_relationships` are responsible for calling `PrincipalCacheInvalidatorPort.invalidate_user(subject_id)` for every affected user subject after the call returns. The session-scoped path inherits this via UoW commit hooks; the engine path requires explicit invalidation."

## 4. Tests

- [ ] 4.1 Integration: patch `SQLModelUserAuthzVersionAdapter.bump_in_session` to raise → call `SQLModelAuthorizationAdapter.write_relationships(...)` → assert the relationship row is absent and the user's `authz_version` is unchanged when read from a fresh connection.
- [ ] 4.2 Integration (happy path): grant a relationship via the engine path → in a separate connection, observe both the `relationships` row and the bumped `authz_version`.
- [ ] 4.3 Unit: `BootstrapSystemAdmin` test calls a fake `PrincipalCache` whose `invalidate_user` method records calls; assert it was called once with the bootstrapped admin's user id.

## 5. Wrap-up

- [ ] 5.1 `make ci` green (line + branch coverage gates intact).
- [ ] 5.2 Manual: with a multi-worker uvicorn (`uvicorn src.main:app --workers 2`), grant a role through the bootstrap path, hit a protected endpoint immediately on the *other* worker, confirm the new permission is honored (no stale principal cache).
