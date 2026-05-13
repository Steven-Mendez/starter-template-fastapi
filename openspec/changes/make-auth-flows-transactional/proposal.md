## Why

`CLAUDE.md` claims that registration, password-reset confirmation, and email-verification confirmation each run inside a single Unit of Work. The code does not match that claim:

1. **`RegisterUser`** (`src/features/authentication/application/use_cases/auth/register_user.py:52-69`) wires three engine-owning repositories. `users.create()`, `credentials.upsert_credential()`, and `audit.record_audit_event()` each open and commit their own session. A crash between writes leaves a `User` row with no `Credential` — the account is unauthenticatable and the email is permanently burned by the `users.email` unique constraint.
2. **`ConfirmPasswordReset`** (`confirm_password_reset.py:68-79`) commits the new password in one transaction (`upsert_credential`) and then runs token consumption + refresh-token revocation + audit in `internal_token_transaction()` separately. A crash after the credential write leaves the new password persisted **while** the reset token is still unconsumed and the old refresh tokens are still valid — the token can be replayed.
3. **`ConfirmEmailVerification`** (`confirm_email_verification.py:31-50`) reads the token with no row lock and writes `mark_verified`/`mark_internal_token_used`/audit in three separate sessions. Two concurrent submissions of the same token both pass the `used_at is None` check and both mark the user verified + record audit events.

All three diverge from the pattern used correctly elsewhere in the codebase (`internal_token_transaction()` + `get_internal_token_for_update`). The fix is uniform: every multi-write use case runs inside one transaction with appropriate row locks.

## What Changes

- Extend `AuthRepositoryPort` with `register_user_transaction()` — a context manager that yields a session-bound writer covering all three writes (user row, credential row, audit event). The `users` feature contributes a session-scoped `UserRegistrarPort` adapter that participates in that session; this mirrors the existing `SessionSQLModelOutboxAdapter` / `SessionSQLModelAuthorizationAdapter` pattern.
- Extend `internal_token_transaction()` and `AuthInternalTokenTransactionPort` so that credential upsert is callable inside the same transaction as token consumption. Refactor `ConfirmPasswordReset` to use it.
- Rewrite `ConfirmEmailVerification` to mirror `ConfirmPasswordReset`: open `internal_token_transaction()`, call `get_internal_token_for_update` (adding the locked variant if it doesn't cover email-verify tokens), mark used, mark verified, audit — all in one transaction.

**Capabilities — Modified**
- `authentication`: tightens the three confirmation/registration requirements to mandate single-transaction execution.

**Capabilities — New**
- None.

## Impact

- **Code**:
  - `src/features/authentication/application/use_cases/auth/register_user.py` — drive all three writes through `register_user_transaction()`. The current `match` on `UserError.DUPLICATE_EMAIL` (line 55) needs to use whichever discriminator landed by `align-error-class-hierarchy`: `isinstance(err, UserAlreadyExistsError)` post-rename. If this change lands first, the existing enum match continues to work and the rebase happens in the error-hierarchy PR.
  - `src/features/authentication/application/use_cases/auth/confirm_password_reset.py` — credential upsert via the in-transaction writer.
  - `src/features/authentication/application/use_cases/auth/confirm_email_verification.py` — locked-read + `mark_user_verified` + token consumption in one transaction.
  - `src/features/authentication/application/ports/repository_port.py` — `register_user_transaction()` context manager on `AuthRepositoryPort`.
  - `src/features/authentication/application/ports/internal_token_port.py` — extend `AuthInternalTokenTransactionPort` writer with `upsert_credential(...)` and `mark_user_verified(...)`.
  - `src/features/authentication/adapters/outbound/persistence/sqlmodel/repository.py` — implementations of both new transactions.
  - `src/features/users/adapters/outbound/persistence/sqlmodel/repository.py` — add `SessionSQLModelUserRegistrarAdapter` (session-scoped); keep the engine-owning adapter.
  - `src/features/authentication/composition/container.py` — instantiate session-scoped writers per transaction; drop the engine-owning user/credentials/audit triple from the registration path.
- **Migrations**: none.
- **Production**: behavioral change is invisible on the happy path. The failure path (crash mid-write) now rolls back cleanly.
- **Tests**:
  - `src/features/authentication/tests/unit/` — fake `register_user_transaction` failing on `upsert_credential`; assert no `UserPort.get_by_email` hit afterwards.
  - `src/features/authentication/tests/integration/` — Postgres-backed: registration with a broken credential write rolls back the user row; the email remains usable.
  - `src/features/authentication/tests/integration/` — concurrency: two threads submit the same email-verification token → exactly one success, exactly one audit event.
  - `src/features/authentication/tests/integration/` — same for password-reset token concurrency.
- **Performance**: marginally faster (fewer commits per use case) and one fewer connection-pool checkout per registration/confirmation.
