## 1. Repository method

- [x] 1.1 Add `invalidate_unused_tokens_for(user_id: UUID, purpose: str) -> int` to the in-transaction writer interface in `src/features/authentication/application/ports/internal_token_port.py`. Return value is the number of rows updated. (Implementation note: the in-transaction writer interface for the issue path is `AuthIssueTokenTransactionPort` in `src/features/authentication/application/ports/outbound/auth_repository.py`; the spec path `internal_token_port.py` does not exist in the current layout, so the method was added to the existing protocol that fronts the issue UoW.)
- [x] 1.2 Implement it on the SQLModel adapter (`src/features/authentication/adapters/outbound/persistence/sqlmodel/repository.py`) via `UPDATE auth_internal_tokens SET used_at = now() WHERE user_id = :uid AND purpose = :purpose AND used_at IS NULL`.

## 2. Wire into use cases

- [x] 2.1 In `src/features/authentication/application/use_cases/auth/request_password_reset.py`, before the existing token insert, call `writer.invalidate_unused_tokens_for(user.id, "password_reset")` inside the same `internal_token_transaction()` Unit of Work.
- [x] 2.2 In `src/features/authentication/application/use_cases/auth/request_email_verification.py`, do the same with `purpose="email_verify"` (the canonical value used at line 57 of that file — NOT `"email_verification"`).

## 3. Tests

- [x] 3.1 Integration test in `src/features/authentication/tests/integration/`: request 3 password resets for the same user; assert only the third token's `used_at IS NULL`; assert the first two have `used_at` set.
- [x] 3.2 Integration test: attempt to confirm with each of the older two tokens; assert the result is `Err(TokenAlreadyUsed)`.
- [x] 3.3 Same pair of tests for email verification. (`ConfirmEmailVerification` updated alongside this change to distinguish `TokenAlreadyUsedError` from `InvalidTokenError`, mirroring `ConfirmPasswordReset` so the spec scenario is honoured.)

## 4. Wrap-up

- [x] 4.1 `make ci` green. (`make test`, `make test-integration`, `make quality`, and `make cov` all pass locally; coverage 84.73% line / 63.07% branch.)
