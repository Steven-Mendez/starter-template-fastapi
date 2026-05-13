## Depends on

- None hard. Composes with `make-auth-flows-transactional` (which extends the deactivate transaction shape) — land `make-auth-flows-transactional` first if both are in flight so the cookie-clear can run after the same Result-returning use case.

## Conflicts with

- `make-auth-flows-transactional`: both touch the deactivate use case's surrounding transaction. Order: `make-auth-flows-transactional` first, then this change adds the cookie clear after the use case returns `Ok`.
- `add-gdpr-erasure-and-export`: both edit `features/users/application/use_cases/deactivate_user.py` and `me.py`. Merge-friction only; no logical conflict.
- `clean-user-assets-on-deactivate`: also edits `me.py` / deactivate flow. Merge-friction only.
- `hide-internal-fields-from-self-views`: also edits `me.py` response shape. Merge-friction only.

## Context

Self-deactivate is a destructive operation. The user expects every artifact of their session to be invalidated — including the cookie that the browser still holds. We do half of that today.

## Decisions

- **Promote `_clear_refresh_cookie` to a public helper**: the alternative (a `CookieClearerPort`) is overkill for one call site. Rationale: one consumer, one obvious shape, no port abstraction needed.
- **Revoke server-side inline (not via outbox)**: `DELETE /me` is a synchronous user action; the response must reflect the revoked state. Call `RevokeAllRefreshTokens(user_id)` inline inside the same Unit of Work that flips `is_active=False`. Rationale: outbox would introduce a window where the cookie is cleared on the browser but server-side refresh still works.
- **Defense in depth**: cookie cleared on the browser, refresh-token family revoked on the server, `is_active=False` flipped on the user — all in one response.

## Risks / Trade-offs

- **Risk**: a client proxy that strips `Set-Cookie`. The inline server-side revocation is the durable defense.

## Migration

Single PR. Backwards compatible.
