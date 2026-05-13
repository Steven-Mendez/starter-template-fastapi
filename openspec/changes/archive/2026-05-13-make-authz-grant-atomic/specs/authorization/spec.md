## ADDED Requirements

### Requirement: AuthorizationPort writes commit relationship and version bump atomically

`AuthorizationPort.write_relationships(...)` and `AuthorizationPort.delete_relationships(...)` SHALL commit the mutation and the matching `authz_version` bump for every affected `user:*` subject in a single database transaction. A failure in either the relationship write or the version bump MUST roll back both.

This requirement applies to both the engine-owning adapter (`SQLModelAuthorizationAdapter`) and the session-scoped adapter (`SessionSQLModelAuthorizationAdapter`).

#### Scenario: Version-bump failure rolls back the relationship write

- **GIVEN** a Postgres-backed `SQLModelAuthorizationAdapter`
- **AND** `UserAuthzVersionPort.bump_in_session` is patched to raise on `user u`
- **WHEN** the adapter is asked to `write_relationships(("system:main", "admin", "user", u.id))`
- **THEN** an exception propagates
- **AND** from a separate connection, the relationship row is absent
- **AND** from a separate connection, `u`'s `authz_version` is unchanged

#### Scenario: Happy path commits exactly once

- **GIVEN** a Postgres-backed `SQLModelAuthorizationAdapter`
- **WHEN** `write_relationships(("system:main", "admin", "user", u.id))` succeeds
- **THEN** exactly one transaction commits to the underlying database
- **AND** both the relationship row and the bumped `authz_version` are visible from a separate connection

### Requirement: UserAuthzVersionPort exposes a session-aware bump

`UserAuthzVersionPort` SHALL declare a `bump_in_session(session, user_id) -> None` method that performs the version increment against the supplied session without committing. The existing engine-owning `bump(user_id)` MAY be implemented as a thin wrapper that opens a transactional scope and delegates to `bump_in_session`.

#### Scenario: `bump_in_session` does not commit

- **GIVEN** an open Session bound to a Postgres connection
- **WHEN** the caller invokes `bump_in_session(session, u.id)` and then rolls back the session
- **THEN** `u`'s `authz_version` is unchanged when read from a fresh connection

### Requirement: Authorization use cases invalidate the principal cache after grant/revoke

The authorization feature SHALL declare a `PrincipalCacheInvalidatorPort` (Protocol with `invalidate_user(user_id) -> None`) under `application/ports/outbound/`. The authentication feature SHALL contribute an adapter wrapping its `PrincipalCache`. Authorization MUST NOT import the auth-side `PrincipalCachePort` directly.

Every use case that calls `AuthorizationPort.write_relationships(...)` or `.delete_relationships(...)` SHALL call `PrincipalCacheInvalidatorPort.invalidate_user(...)` for every affected `user:*` subject after the call returns. Invalidation is best-effort: any `Exception` raised by the invalidator MUST be logged at WARNING and swallowed, NOT propagated to the use-case caller.

#### Scenario: BootstrapSystemAdmin invalidates the cache

- **GIVEN** a `BootstrapSystemAdmin` wired with a fake `PrincipalCacheInvalidator`
- **WHEN** the use case successfully grants `system:main#admin` to user `u`
- **THEN** the fake's `invalidate_user` method was called exactly once with `u.id`

#### Scenario: Cache invalidation failure is swallowed

- **GIVEN** a `BootstrapSystemAdmin` wired with an invalidator whose `invalidate_user` raises `RuntimeError("redis down")`
- **WHEN** the use case grants `system:main#admin` to user `u`
- **THEN** the use case completes and returns `u.id`
- **AND** a WARNING log entry is emitted including the error reason
- **AND** the relationship row was committed (the cache failure does not roll back the DB)
