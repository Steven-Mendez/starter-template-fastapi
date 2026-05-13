## 1. Cross-feature registration UoW

- [ ] 1.1 Add `register_user_transaction()` context manager to `AuthRepositoryPort` (`src/features/authentication/application/ports/repository_port.py`) yielding a writer that exposes `create_user(...)`, `upsert_credential(...)`, `record_audit_event(...)`.
- [ ] 1.2 Implement on the SQLModel adapter (`src/features/authentication/adapters/outbound/persistence/sqlmodel/repository.py`) using a single `Session` + `session.commit()` at context exit.
- [ ] 1.3 Add `SessionSQLModelUserRegistrarAdapter` (or extend the existing `SessionSQLModelUserRepository`) that accepts a `Session` and writes the `UserTable` row without owning the commit.
- [ ] 1.4 Wire it through `users` feature composition so the auth container can instantiate it per-transaction.
- [ ] 1.5 Refactor `RegisterUser.execute` to drive all three writes through the new transaction handle. Remove the engine-owning `UserPort.create` call from the registration path.

## 2. Password-reset confirm UoW

- [ ] 2.1 Extend `AuthInternalTokenTransactionPort` (`src/features/authentication/application/ports/internal_token_port.py`) with `upsert_credential(...)` on the in-transaction writer.
- [ ] 2.2 Implement on the SQLModel adapter so the credential write commits with the token consumption.
- [ ] 2.3 Refactor `ConfirmPasswordReset.execute` (`confirm_password_reset.py`) to call the in-txn `upsert_credential` instead of the engine-owning `credentials` adapter.
- [ ] 2.4 Drop the now-unused engine-owning `upsert_credential` call from the use case.

## 3. Email-verification confirm UoW

- [ ] 3.1 Confirm `get_internal_token_for_update` covers the email-verification token kind; if not, extend the writer to take a `kind` argument that selects the row-lock query.
- [ ] 3.2 Add `mark_user_verified(user_id)` to the in-txn writer.
- [ ] 3.3 Rewrite `ConfirmEmailVerification.execute` in `src/features/authentication/application/use_cases/auth/confirm_email_verification.py`:
  - [ ] 3.3.1 Open `internal_token_transaction()` as `tx` (replacing the current three engine-owning calls at lines 31, 43-44, 47).
  - [ ] 3.3.2 Fetch the token via `tx.get_internal_token_for_update(...)`; branch on `used_at`/`expires_at`/`user_id` exactly as today.
  - [ ] 3.3.3 On the happy branch, call `tx.mark_user_verified(user_id)`, `tx.mark_internal_token_used(record.id)`, and `tx.record_audit_event(event_type="auth.email_verified", user_id=...)` — all on the same writer.
  - [ ] 3.3.4 Keep the post-commit `self._cache.invalidate_user(...)` call outside the context so cache invalidation only fires after the transaction commits.

## 4. Regression tests

- [ ] 4.1 Unit: register-user uses a fake `register_user_transaction` that fails on `upsert_credential` → assert the user row was not committed (no `UserPort.get_by_email` hit afterwards).
- [ ] 4.2 Integration (Postgres): registration with a deliberately broken credential write rolls back the user row; the email remains usable on the next attempt.
- [ ] 4.3 Unit: confirm-password-reset with the in-txn writer raising after `upsert_credential` → assert the reset token is still unused and refresh tokens are still valid (everything rolls back together).
- [ ] 4.4 Integration: two threads submit the same email-verification token concurrently → exactly one succeeds, exactly one `auth.email_verification.confirmed` audit event is recorded.
- [ ] 4.5 Concurrency test for password-reset confirm: two threads submit the same reset token → exactly one succeeds.

## 5. Wiring & docs

- [ ] 5.1 Update `src/features/authentication/composition/container.py` to construct the session-scoped writers (no longer needs the engine-owning user/credentials/audit triple in the registration path).
- [ ] 5.2 Update `CLAUDE.md` Architecture section: replace "delegates user creation to `users`" with the more precise "writes through a session-scoped `UserRegistrarPort` adapter inside the registration transaction".
- [ ] 5.3 `make ci` green; `make lint-arch` still passes (no new cross-feature direct imports — the new adapter is wired through composition only).

## 6. Wrap-up

- [ ] 6.1 Manual: register → simulate crash by killing the dev server between writes (e.g. inject a `raise` after `create_user`); restart; confirm the email is still usable.
