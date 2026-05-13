## 1. Repository method

- [ ] 1.1 Add `invalidate_unused_tokens_for(user_id: UUID, purpose: str) -> int` to the in-transaction writer interface in `src/features/authentication/application/ports/internal_token_port.py`. Return value is the number of rows updated.
- [ ] 1.2 Implement it on the SQLModel adapter (`src/features/authentication/adapters/outbound/persistence/sqlmodel/repository.py`) via `UPDATE auth_internal_tokens SET used_at = now() WHERE user_id = :uid AND purpose = :purpose AND used_at IS NULL`.

## 2. Wire into use cases

- [ ] 2.1 In `src/features/authentication/application/use_cases/auth/request_password_reset.py`, before the existing token insert, call `writer.invalidate_unused_tokens_for(user.id, "password_reset")` inside the same `internal_token_transaction()` Unit of Work.
- [ ] 2.2 In `src/features/authentication/application/use_cases/auth/request_email_verification.py`, do the same with `purpose="email_verify"` (the canonical value used at line 57 of that file — NOT `"email_verification"`).

## 3. Tests

- [ ] 3.1 Integration test in `src/features/authentication/tests/integration/`: request 3 password resets for the same user; assert only the third token's `used_at IS NULL`; assert the first two have `used_at` set.
- [ ] 3.2 Integration test: attempt to confirm with each of the older two tokens; assert the result is `Err(TokenAlreadyUsed)`.
- [ ] 3.3 Same pair of tests for email verification.

## 4. Wrap-up

- [ ] 4.1 `make ci` green.
