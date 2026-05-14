## 1. Expose the cookie helper

- [x] 1.1 Create `src/features/authentication/adapters/inbound/http/cookies.py` and define `clear_refresh_cookie(response: Response, request: Request) -> None` by lifting the body of the current private `_clear_refresh_cookie` from `auth.py`.
- [x] 1.2 Re-export `clear_refresh_cookie` from `src/features/authentication/adapters/inbound/http/__init__.py`.
- [x] 1.3 In `src/features/authentication/adapters/inbound/http/auth.py`, replace every call site of `_clear_refresh_cookie` with the new public helper and delete the local function.

## 2. Use it in DELETE /me

- [x] 2.1 In `src/features/users/adapters/inbound/http/me.py`, inject `Response` and `Request` into the `DELETE /me` handler signature.
- [x] 2.2 After `result.is_ok()` returns true, call `clear_refresh_cookie(response, request)` inline (no outbox enqueue).
- [x] 2.3 Wire a `RevokeAllRefreshTokens` collaborator into `DeactivateUser` (or a wrapping coordinator on the route):
  - [x] 2.3.1 Accept a `revoke_all_refresh_tokens` callable on `src/features/users/application/use_cases/deactivate_user.py` (or, if kept on the route, pass it through the route handler).
  - [x] 2.3.2 Invoke it inline inside the same Unit of Work that flips `is_active=False` so the server-side refresh-token families are revoked before the response is returned.
  - [x] 2.3.3 Wire the collaborator in `src/features/users/composition/container.py` (or the route container) from the authentication container's existing revoke use case.

## 3. Tests

- [x] 3.1 e2e in `src/features/users/tests/e2e/`: authenticate, call `DELETE /me`, assert response includes `Set-Cookie: refresh_token=; Max-Age=0; Path=/auth`.
- [x] 3.2 e2e: after self-deactivate, replay the still-stored refresh cookie against `POST /auth/refresh`; assert the response is 401.
- [x] 3.3 Unit: `DeactivateUser` test asserts `RevokeAllRefreshTokens` is invoked for the same `user_id` in the same Unit of Work.

## 4. Wrap-up

- [x] 4.1 Update `docs/api.md` `DELETE /me` section to document the `Set-Cookie` clear and the server-side revocation.
- [x] 4.2 `make ci` green.
