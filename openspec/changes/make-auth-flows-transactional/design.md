## Depends on

- `clean-architecture-seams` — relocates `management.py` and introduces the `OutboxUnitOfWorkPort`. Land it first (or co-land) so the new `register_user_transaction()` composes with the same UoW conventions.

## Conflicts with

- `invalidate-previous-issuance-tokens` — extends the in-transaction writer added here. Order: this change first; `invalidate-previous-issuance-tokens` second.
- `clear-refresh-cookie-on-self-deactivate` — relies on the `RevokeAllRefreshTokens(user_id)` collaborator being callable inline; that collaborator's Unit-of-Work shape is the same one this change introduces. Order: this change first.
- `clean-architecture-seams`: shares `src/features/authentication/composition/container.py`.
- `improve-db-performance`: shares the users SQLModel repository.
- `fix-bootstrap-admin-escalation`: shares the session-scoped `UserRegistrarPort` cousin (`CredentialVerifierPort`); merge friction only.

## Context

The repository advertises hexagonal architecture with explicit Unit-of-Work seams for any flow that mutates more than one table. `outbox` already follows the pattern: `SessionSQLModelOutboxAdapter` accepts an external `Session` and participates in the surrounding transaction. `authorization` does the same with `SessionSQLModelAuthorizationAdapter`. Registration and confirm-flows in `authentication` were left on the older "engine-per-repo" shape, which means they look correct from the outside (calls chain neatly) but actually commit three separate transactions.

The cross-feature shape is what makes this awkward: registration writes to `users.users` *and* `authentication.credentials` *and* `authentication.audit_events`. The first table is owned by another feature. The fix has to introduce a session-scoped writer that bridges the boundary without breaking the import-linter rule that says `authentication` cannot reach into `users.adapters`.

## Goals / Non-Goals

**Goals**
- Every use case that mutates more than one row commits exactly one transaction.
- All three confirmation/registration use cases lock the relevant row when they read it (`FOR UPDATE`) so concurrent requests cannot both pass a precondition check.
- Cross-feature boundaries preserved: `authentication` still does not import `users.adapters`; it depends on a `UserRegistrarPort` that `users` implements in two flavors (engine-owning + session-scoped).

**Non-Goals**
- Reworking every other engine-owning repository in the codebase.
- Adding a generic `UnitOfWork[T]` abstraction.

## Decisions

### Decision 1: Extend the existing context-manager pattern, don't introduce `UnitOfWork`

- **Chosen**: add a `register_user_transaction()` context manager on `AuthRepositoryPort` that yields a writer interface (`create_user`, `upsert_credential`, `record_audit_event`). Mirrors the existing `internal_token_transaction()`.
- **Rationale**: keeps the codebase's existing pattern uniform; no new abstraction.
- **Rejected**: a generic `UnitOfWork.session()`. Leaks SQLModel types into every consumer.

### Decision 2: Session-scoped `UserRegistrarPort` adapter contributed by `users`

- **Chosen**: `users` ships two adapters — the existing engine-owning `SQLModelUserRegistrarAdapter` and a new `SessionSQLModelUserRegistrarAdapter` constructed inside `register_user_transaction()` with the bound session.
- **Rationale**: preserves the cross-feature import boundary.
- **Rejected**: `authentication` writing directly into the `users` table.

### Decision 3: One transaction shape per use case, not a shared monolith

- **Chosen**: `register_user_transaction()` is distinct from `internal_token_transaction()`.
- **Rationale**: distinct tables and lock semantics; sharing would inflate the writer's surface.

### Decision 4: Read-then-update under `FOR UPDATE` in `ConfirmEmailVerification`

- **Chosen**: mirror `ConfirmPasswordReset`'s locked-read pattern.
- **Rationale**: without the row lock, two threads can both pass the `used_at IS NULL` check; the locked read serializes them.

## Risks / Trade-offs

- **Risk**: the new session-scoped `UserRegistrarPort` adapter duplicates a subset of the engine-owning version. Mitigation: extract the common SQL into a private `_user_table_insert(session, …)` helper used by both adapters.
- **Risk**: longer transactions hold connections marginally longer. Negligible under reasonable pool sizing; flagged in `improve-db-performance` separately.
- **Trade-off**: extending `AuthInternalTokenTransactionPort` with `upsert_credential` and `mark_user_verified` widens the writer. Acceptable — these are all "things that must commit with the token consumption" and the port is internal to `authentication`.

## Migration Plan

Single PR. No data migration. Land in this order:

1. New session-scoped `UserRegistrarPort` adapter in `users`.
2. New `register_user_transaction()` on the auth repo port + SQLModel adapter.
3. Refactor `RegisterUser`.
4. Extend `internal_token_transaction()` with credential upsert + mark-verified.
5. Refactor `ConfirmPasswordReset` and `ConfirmEmailVerification`.
6. Tests (unit + Postgres-backed concurrency tests).

Rollback: revert; no schema or data depends on this work.
