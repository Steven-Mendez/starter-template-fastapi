## Why

`UserPublic` (`features/users/adapters/inbound/http/schemas.py:18`) is returned from `GET /me` and includes `authz_version` — an internal cache-invalidation counter. Returning it lets a client infer permission-change history (they were granted a role, then it was revoked). Useful field on admin views; leak on self-views.

## What Changes

- Define a `UserPublicSelf(BaseModel)` schema with the same fields as `UserPublic` minus the redacted set.
- `GET /me` and `PATCH /me` respond with `UserPublicSelf`.
- `GET /admin/users` and any admin route keep returning `UserPublic`.

**Redacted field set on self-views.** The exhaustive list of `UserPublic` fields removed from `UserPublicSelf` is:

- `authz_version` — internal cache-invalidation counter; leaks permission-change history.

That is the entire set. `created_at` is retained — it is non-sensitive and useful to the user. `password_hash` is **not** in scope: the `User` entity no longer carries a password hash; credentials live in the `authentication` feature's `credentials` table and were never on `UserPublic`. The unit test from the design (symmetric-difference of fields) MUST encode exactly `{"authz_version"}` so any future addition to either schema forces a deliberate decision.

**Capabilities — Modified**: `users` (via project-layout spec — the rule is "self-views don't expose internal counters").

## Depends on

- None.

## Conflicts with

- `clear-refresh-cookie-on-self-deactivate` — also edits `src/features/users/adapters/inbound/http/me.py`. Whichever lands second rebases its handler signatures onto the new `response_model=UserPublicSelf`.

## Impact

- **Code (modified)**: `src/features/users/adapters/inbound/http/schemas.py` (add `UserPublicSelf`), `src/features/users/adapters/inbound/http/me.py` (`GET /me` and `PATCH /me` switch `response_model`), `docs/api.md` (note the split).
- **OpenAPI**: a new `UserPublicSelf` schema appears alongside `UserPublic`; SDK regenerations pick it up. `GET /me` and `PATCH /me` reference the new schema.
- **Tests**: e2e asserts `GET /me` response body does NOT contain `authz_version`; e2e asserts `GET /admin/users` DOES contain it; unit test pins the symmetric-difference of `UserPublic` and `UserPublicSelf` fields to `{"authz_version"}`.
