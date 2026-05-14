## Why

`RequestPasswordReset` and `RequestEmailVerification` both insert a fresh token row without invalidating previous unused tokens for the same user + purpose (`request_password_reset.py:55-84`, `request_email_verification.py:54-83`). If a user clicks "Send again" 5 times, all 5 raw tokens are independently valid until expiry — perfect for phishing where an attacker captures one of the earlier emails.

## What Changes

- Add `invalidate_unused_tokens_for(user_id, purpose)` to the internal-token writer interface; emits `UPDATE auth_internal_tokens SET used_at = now() WHERE user_id = :uid AND purpose = :purpose AND used_at IS NULL`.
- Call it from inside the same in-transaction Unit of Work (introduced by `make-auth-flows-transactional`) that inserts the new token, in both `RequestPasswordReset.execute` and `RequestEmailVerification.execute`.

**Capabilities — Modified**: `authentication`.

## Impact

- **Code**:
  - `src/features/authentication/application/ports/internal_token_port.py` — add `invalidate_unused_tokens_for(user_id, purpose)` to the in-transaction writer interface.
  - `src/features/authentication/adapters/outbound/persistence/sqlmodel/repository.py` — implement the new method via the documented `UPDATE`.
  - `src/features/authentication/application/use_cases/auth/request_password_reset.py` — call `writer.invalidate_unused_tokens_for(user.id, "password_reset")` before inserting the new token.
  - `src/features/authentication/application/use_cases/auth/request_email_verification.py` — same call with `purpose="email_verify"` (the canonical value used in that file at line 57; NOT `"email_verification"`).
- **Migrations**: none.
- **Tests**:
  - `src/features/authentication/tests/integration/` — request 3 password resets for the same user; assert only the latest token has `used_at IS NULL`; assert older tokens have `used_at` set; assert a confirm attempt with an older token returns `Err(TokenAlreadyUsed)`.
- **Production**: closes the "captured an older email" phishing surface.
