## 1. Schemas

- [x] 1.1 Add `UserPublicSelf(BaseModel)` in `src/features/users/adapters/inbound/http/schemas.py` mirroring `UserPublic` exactly minus `authz_version`. Verified field set retained (`UserPublic` at `schemas.py:11-22`): `id`, `email`, `is_active`, `is_verified`, `created_at`, `updated_at`. Carry the same `model_config = ConfigDict(from_attributes=True)`.
- [x] 1.2 Switch `GET /me` and `PATCH /me` in `src/features/users/adapters/inbound/http/me.py` to `response_model=UserPublicSelf`.
- [x] 1.3 Leave `GET /admin/users` and other admin endpoints on `UserPublic`.

## 2. Tests

- [x] 2.1 Add an e2e test asserting `GET /me` response body does NOT contain the key `authz_version`.
- [x] 2.2 Add an e2e test asserting `GET /admin/users` response body for an admin caller DOES contain `authz_version` for every user object.
- [x] 2.3 Add a unit test pinning the symmetric difference of `UserPublic.model_fields` and `UserPublicSelf.model_fields` to exactly `{"authz_version"}`.

## 3. Docs

- [x] 3.1 Document the self-view vs admin-view split in `docs/api.md`, listing the redacted field set explicitly.
- [x] 3.2 Run `make ci` and confirm it is green.
