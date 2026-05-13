## Why

`src/features/users/adapters/inbound/http/me.py:72-87` handles self-deactivation but never clears the refresh cookie. The browser keeps a valid `refresh_token` cookie scoped to `/auth`. Depending on session-revocation timing, the deactivated user can hit `POST /auth/refresh` and keep working. Even if revocation eventually wins, the cookie should be cleared at the source.

## What Changes

- Move `_clear_refresh_cookie` from `src/features/authentication/adapters/inbound/http/auth.py` to a new public helper `src/features/authentication/adapters/inbound/http/cookies.py:clear_refresh_cookie`.
- Re-export it from `src/features/authentication/adapters/inbound/http/__init__.py`.
- Inject `Response` and `Request` into the `DELETE /me` handler in `src/features/users/adapters/inbound/http/me.py`.
- After the `DeactivateUser` use case returns `Ok`, call `clear_refresh_cookie(response, request)` inline (synchronous user action — no outbox).
- Call `RevokeAllRefreshTokens(user_id)` inline inside the same Unit of Work as the `is_active=False` flip so server-side refresh-token families are dead before the response goes out.

**Capabilities — Modified**: `authentication`.

## Impact

- **Code**:
  - `src/features/authentication/adapters/inbound/http/cookies.py` (new) — `clear_refresh_cookie(response, request)` helper.
  - `src/features/authentication/adapters/inbound/http/auth.py` — replace inline `_clear_refresh_cookie` with import from the new module.
  - `src/features/authentication/adapters/inbound/http/__init__.py` — re-export `clear_refresh_cookie`.
  - `src/features/users/adapters/inbound/http/me.py` — `DELETE /me` injects `Response`, calls `clear_refresh_cookie`, invokes `RevokeAllRefreshTokens(user_id)` inline.
  - `src/features/users/application/use_cases/deactivate_user.py` — accept a `revoke_all_refresh_tokens` collaborator (or call into a use case the container wires).
- **Docs**: `docs/api.md` — describe the deactivate flow's cookie behavior.
- **Tests**: `src/features/users/tests/e2e/` — assert `Set-Cookie: refresh_token=; Max-Age=0` on `DELETE /me`; assert subsequent `POST /auth/refresh` with the captured cookie returns 401.
