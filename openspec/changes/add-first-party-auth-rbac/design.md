## Context

### Project Inspection Findings

- Folder structure: feature-first hexagonal architecture under `src/features/<feature>`, shared platform code under `src/platform`, Alembic migrations under `alembic/versions`, tests colocated under each feature.
- FastAPI version/style: `fastapi==0.135.3`, app factory in `src/platform/api/app_factory.py`, app entrypoint `src.main:app`, routes mounted eagerly before lifespan, dependencies use `Annotated` aliases in existing code.
- Configuration: `pydantic-settings==2.13.1` with `AppSettings`, `env_prefix="APP_"`, `.env`, and `extra="ignore"`.
- PostgreSQL connection: `APP_POSTGRESQL_DSN`, default `postgresql+psycopg://...`, sync SQLModel engine and sessions.
- Installed libraries: FastAPI, Starlette, SQLAlchemy 2, Alembic, SQLModel, Pydantic 2, pydantic-settings, psycopg 3, pytest, httpx, testcontainers. PyJWT, pwdlib, and argon2-cffi were not installed at inspection time.
- Existing auth/user/RBAC models: none found. Existing write protection is optional `X-API-Key` on Kanban write routers.
- Migrations: Alembic exists with two Kanban migrations. Metadata comes from SQLModel via `get_sqlmodel_metadata()`.
- Tests: pytest discovers under `src`, with `unit`, `integration`, and `e2e` markers. E2E uses FastAPI `TestClient`; integration persistence uses testcontainers PostgreSQL when Docker is available.
- Context7/MCP availability: Context7 tools are available in this environment. OpenCode config permits skills; no repo-local MCP server config was required.
- OpenSpec availability: `openspec/config.yaml` exists with `schema: spec-driven`; no active changes existed before this one.
- Existing admin/protected resources: no admin endpoints. Kanban write endpoints optionally require `APP_WRITE_API_KEY` and must remain compatible.
- Tenancy: no tenant, workspace, organization, or account partitioning was detected. Treat the app as single-tenant for this change.

## Goals / Non-Goals

**Goals:**

- Implement first-party auth and persistent RBAC as a new `auth` feature without replacing platform or Kanban structure.
- Use SQLModel sync persistence, PostgreSQL, and Alembic because this is the clear existing stack.
- Keep access tokens short-lived JWTs and refresh tokens opaque, rotated, revocable, and stored only as hashes.
- Enforce least privilege through explicit persisted permissions.
- Provide a secure path to bootstrap the first `super_admin` outside public registration.
- Add tests for happy paths and security failure paths.

**Non-Goals:**

- No external auth providers, Redis, Celery, distributed cache, OAuth provider setup, ABAC, or PBAC.
- No conversion to SQLAlchemy async in this change; it would be a broad architectural migration not required by the detected stack.
- No recommendation to store tokens in localStorage.
- No implicit permission grant solely because a role is named `admin`.

## Decisions

### 1. Feature Placement

Decision: add `src/features/auth` with inbound HTTP adapters, outbound SQLModel persistence, service layer, schemas, dependencies, and composition wiring.

Rationale: the project documents feature-first hexagonal architecture and mounts Kanban through feature composition. Auth/RBAC is a business capability with its own persistence and HTTP surface, while platform remains feature-agnostic.

Alternative considered: put all auth code in `src/platform`. Rejected because platform contracts forbid feature dependencies and platform currently owns only cross-cutting mechanics, not business data models.

### 2. ORM And Driver

Decision: use SQLModel sync models and repositories with SQLAlchemy 2-compatible Core constructs and psycopg 3 URLs.

Rationale: the repo already uses `sqlmodel==0.0.38`, sync `Session`, `create_engine`, PostgreSQL DSN `postgresql+psycopg`, and Alembic metadata from `SQLModel.metadata`.

Alternative considered: SQLAlchemy 2 async plus asyncpg. Rejected for this change because there is a clear existing sync SQLModel/psycopg stack and switching would risk breaking current architecture.

### 3. Authentication Token Strategy

Decision: return a short-lived JWT access token in JSON and accept it via `Authorization: Bearer`; issue an opaque refresh token in an HttpOnly cookie and store only a SHA-256 hash of that opaque token in PostgreSQL.

Rationale: bearer access tokens are explicit and avoid localStorage recommendations, while refresh cookies reduce accidental token exposure. Hashing refresh tokens limits database disclosure impact.

Alternative considered: long-lived JWT-only sessions. Rejected because revocation and rotation are weaker.

Cookie defaults:

- Cookie name: `refresh_token`.
- `httponly=True`.
- `secure` from `AUTH_COOKIE_SECURE`.
- `samesite` from `AUTH_COOKIE_SAMESITE`, default `lax` for development compatibility, configurable to `strict`.
- Path `/auth` so the cookie is not sent to unrelated API routes.

### 4. JWT Claims

Decision: access tokens include `sub`, `exp`, `iat`, `nbf`, `jti`, `roles`, and `authz_version`; include `iss` and `aud` only when configured.

Rationale: Context7 PyJWT docs confirm validation of `exp`, `nbf`, `iat`, issuer, audience, algorithms, and required claims. Roles are low-cardinality and useful for display/auditing, while permissions can change frequently.

Permissions are not required to be embedded in the JWT. Authorization dependencies load the current user, active roles, and permissions from PostgreSQL and compare token `authz_version` to `users.authz_version`. A mismatch returns `401`, making stale access tokens unusable after RBAC changes.

### 5. Password Hashing

Decision: use `argon2-cffi` `PasswordHasher`, which defaults to Argon2id-compatible secure hashing and provides `verify()` and `check_needs_rehash()`.

Rationale: Context7 resolved `argon2-cffi` as a high-reputation maintained package and confirmed `PasswordHasher` usage. Context7 did not resolve `pwdlib` directly in this environment, although FastAPI docs referenced it, so direct Argon2-cffi avoids an undocumented dependency.

### 6. Data Model

#### `users`

- `id`: UUID primary key.
- `email`: normalized lowercase string, unique.
- `password_hash`: string.
- `is_active`: bool, default true.
- `is_verified`: bool, default false.
- `authz_version`: integer, default 1.
- `created_at`, `updated_at`: timezone-aware timestamps.
- `last_login_at`: nullable timestamp.

Indexes/constraints:

- Unique constraint on `email`.
- Check constraint for `authz_version >= 1`.

#### `roles`

- `id`: UUID primary key.
- `name`: unique normalized string, e.g. `super_admin`, `admin`, `manager`, `user`.
- `description`: nullable string.
- `is_active`: bool, default true.
- `created_at`, `updated_at`: timezone-aware timestamps.

Indexes/constraints:

- Unique constraint on `name`.
- Check constraint enforcing lowercase-ish normalized role names through application validation; DB check may use a conservative pattern where practical.

#### `permissions`

- `id`: UUID primary key.
- `name`: unique normalized string in `resource:action` format.
- `description`: nullable string.
- `created_at`, `updated_at`: timezone-aware timestamps.

Indexes/constraints:

- Unique constraint on `name`.
- Check constraint requiring `name` to contain `:`.

#### `user_roles`

- `user_id`: FK to `users.id`, cascade delete.
- `role_id`: FK to `roles.id`, cascade delete.
- `created_at`: timezone-aware timestamp.
- Primary key or unique constraint on `(user_id, role_id)`.

Indexes:

- Index on `user_id`.
- Index on `role_id`.

#### `role_permissions`

- `role_id`: FK to `roles.id`, cascade delete.
- `permission_id`: FK to `permissions.id`, cascade delete.
- `created_at`: timezone-aware timestamp.
- Primary key or unique constraint on `(role_id, permission_id)`.

Indexes:

- Index on `role_id`.
- Index on `permission_id`.

#### `refresh_tokens`

- `id`: UUID primary key.
- `user_id`: FK to `users.id`, cascade delete.
- `token_hash`: unique string.
- `family_id`: UUID for rotation family.
- `expires_at`: timezone-aware timestamp.
- `revoked_at`: nullable timestamp.
- `replaced_by_token_id`: nullable FK to `refresh_tokens.id`.
- `created_at`: timezone-aware timestamp.
- `created_ip`: nullable string.
- `user_agent`: nullable string.

Indexes:

- Unique index on `token_hash`.
- Index on `user_id`.
- Index on `family_id`.
- Index on `expires_at`.

#### `auth_audit_events`

- `id`: UUID primary key.
- `user_id`: nullable FK to `users.id`.
- `event_type`: string.
- `ip_address`: nullable string.
- `user_agent`: nullable string.
- `metadata`: PostgreSQL JSONB.
- `created_at`: timezone-aware timestamp.

Indexes:

- Index on `user_id`.
- Index on `event_type`.
- Index on `created_at`.

#### `auth_internal_tokens`

- `id`: UUID primary key.
- `user_id`: nullable FK to `users.id`.
- `purpose`: string, `password_reset` or `email_verify`.
- `token_hash`: unique string.
- `expires_at`: timezone-aware timestamp.
- `used_at`: nullable timestamp.
- `created_at`: timezone-aware timestamp.
- `created_ip`: nullable string.

Indexes:

- Unique index on `token_hash`.
- Index on `(user_id, purpose)`.
- Index on `expires_at`.

### 7. Permission Convention

Decision: permission names use normalized `resource:action` strings.

Examples:

- `users:read`
- `users:create`
- `users:update`
- `users:delete`
- `users:roles:manage`
- `roles:read`
- `roles:manage`
- `permissions:read`
- `permissions:manage`
- `auth:sessions:revoke`
- `admin:access`

Rationale: names are human-readable, compact, and testable. Ambiguous booleans like `admin=true` are not sufficient authorization controls.

### 8. Initial Roles

Decision: seed these roles and permissions explicitly:

- `super_admin`: all seeded permissions.
- `admin`: operational management permissions, excluding critical global-only actions if added later.
- `manager`: read and limited operations.
- `user`: own-account basic permissions only.

The default role for public registration is configured by `AUTH_DEFAULT_USER_ROLE` and defaults to `user`. If that role does not exist, registration still succeeds but grants no administrative role.

### 9. First Admin Bootstrap

Decision: provide a management command such as `python -m src.features.auth.management create_super_admin --email <email> --password-env AUTH_BOOTSTRAP_PASSWORD` plus a seed command for roles/permissions.

Rationale: the first privileged user must not be promotable through public registration. Using a CLI with an environment-provided password keeps secrets out of command history and fixtures.

### 10. Auth Flows

#### Registration

- Normalize email to lowercase and trim whitespace.
- Reject duplicate email with a safe `409` response.
- Hash password using Argon2id.
- Create user with `is_active=True`, `is_verified=False`, `authz_version=1`.
- Assign default non-admin role if configured and present.
- Emit audit event.

#### Login

- Accept email/password.
- Return a generic invalid-credentials error for unknown email, inactive user, or wrong password where possible.
- Verify password hash.
- Update `last_login_at`.
- Issue access token and refresh token.
- Store refresh token hash, family id, expiry, IP, and user-agent.
- Set refresh token cookie.

#### Refresh

- Read refresh token from HttpOnly cookie by default, with optional body fallback only for non-browser clients if enabled later.
- Hash incoming token and look up a non-expired record.
- If the record is revoked and reused, revoke all tokens in the same family and return `401`.
- If valid, revoke old token, create replacement in same family, link `replaced_by_token_id`, return a new access token, and set a new refresh cookie.
- Access token uses current roles and current `users.authz_version`.

#### Logout

- Revoke the current refresh token when present.
- Delete the refresh cookie.
- Return success even if the token is already absent, without leaking session existence.

#### Logout-All

- Require a valid active user.
- Revoke all non-revoked refresh tokens for the current user.
- Delete the refresh cookie.
- Emit audit event.

#### Password Reset

- Forgot password creates an opaque internal token hash with purpose `password_reset` and expiration.
- The API returns a generic response regardless of whether the email exists.
- Reset verifies the opaque token, updates password hash, marks token used, revokes all refresh sessions, and increments `authz_version`.
- Delivery integration is out of scope; in development/tests the raw token may be returned only when explicitly enabled by test/development settings.

#### Email Verification

- Verification request creates an opaque internal token hash with purpose `email_verify` and expiration.
- Verify consumes the token and sets `is_verified=True`.
- Delivery integration is out of scope; development/test token exposure follows the same explicit setting as password reset.

### 11. Authorization Dependencies

Decision: expose these FastAPI dependencies from the auth inbound layer:

- `get_current_user()`
- `get_current_principal()` for user plus active roles and permissions.
- `require_active_user()`
- `require_roles(*roles)`
- `require_permissions(*permissions)`
- `require_any_permission(*permissions)`
- `require_all_permissions(*permissions)`

Behavior:

- Missing, malformed, invalid, expired, or stale tokens return `401` with `WWW-Authenticate: Bearer`.
- Authenticated users without required permission return `403`.
- Inactive users return `403` after authentication succeeds.
- Inactive roles grant no permissions.

### 12. Admin RBAC Endpoints

Decision: mount admin routes at `/admin`:

- `GET /admin/roles`: requires `roles:read` or `roles:manage`.
- `POST /admin/roles`: requires `roles:manage`.
- `PATCH /admin/roles/{role_id}`: requires `roles:manage`.
- `GET /admin/permissions`: requires `permissions:read` or `permissions:manage`.
- `POST /admin/permissions`: requires `permissions:manage`.
- `POST /admin/roles/{role_id}/permissions`: requires `permissions:manage`.
- `DELETE /admin/roles/{role_id}/permissions/{permission_id}`: requires `permissions:manage`.
- `POST /admin/users/{user_id}/roles`: requires `users:roles:manage`.
- `DELETE /admin/users/{user_id}/roles/{role_id}`: requires `users:roles:manage`.

Every RBAC mutation emits `auth_audit_events` and updates affected user `authz_version` values:

- User role changes increment the target user's `authz_version`.
- Role permission changes increment `authz_version` for users assigned to that role.
- Deactivating a role increments `authz_version` for assigned users.

### 13. Configuration

Settings are added to `AppSettings` with `APP_` prefixed environment variables:

- `AUTH_JWT_SECRET_KEY`
- `AUTH_JWT_ALGORITHM`
- `AUTH_JWT_ISSUER`
- `AUTH_JWT_AUDIENCE`
- `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`
- `AUTH_REFRESH_TOKEN_EXPIRE_DAYS`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`
- `AUTH_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`
- `AUTH_EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES`
- `AUTH_RATE_LIMIT_ENABLED`
- `AUTH_RBAC_ENABLED`
- `AUTH_DEFAULT_USER_ROLE`
- `AUTH_SUPER_ADMIN_ROLE`

Implementation note: because the existing settings model uses `env_prefix="APP_"`, the actual environment variables are `APP_AUTH_*` unless field aliases are introduced. `.env.example` will document the project-compatible `APP_AUTH_*` names and note the user-facing auth setting names.

No real secrets are generated or committed.

### 14. CSRF And Cookie Safety

Decision: access-token protected endpoints use `Authorization: Bearer`, not cookies. Refresh/logout cookie endpoints use HttpOnly refresh cookie, SameSite protection, and an Origin check when an `Origin` header is present and configured CORS origins are not wildcard.

Rationale: SameSite Lax/Strict prevents common cross-site POST refresh attacks. Origin checks provide an additional local guard without external services. This initial version does not introduce a browser-visible CSRF token cookie unless future UI requirements require it.

### 15. Rate Limiting

Decision: implement a small in-memory, process-local rate limiter for sensitive endpoints (`/auth/login`, `/auth/password/forgot`, `/auth/password/reset`, verification requests).

Rationale: user explicitly excludes Redis/external services. This is replaceable and disabled by `AUTH_RATE_LIMIT_ENABLED=false`.

Trade-off: limits are not shared across workers or processes.

### 16. Audit And Observability

Decision: persist security-relevant audit events and log only safe metadata.

Events include registration, login success/failure, refresh reuse detection, logout-all, password reset request/complete, email verification, role creation/update, permission creation, role-permission changes, and user-role changes.

Logs must not include passwords, raw tokens, full hashes, JWTs, or secret settings.

### 17. Multi-Tenant/RLS Guidance

The app is currently single-tenant. If tenant models are introduced later, auth tables should gain tenant scoping where appropriate, and PostgreSQL Row Level Security policies should be evaluated for tenant-owned business data. RBAC alone is not a tenant-isolation mechanism.

### 18. Testing Strategy

- Unit tests for password hashing, token encode/decode, token hashing, rate limiter, and permission checks.
- E2E tests with in-memory auth repository and `TestClient` for auth and RBAC flows.
- Integration tests for SQLModel persistence can be added using the existing testcontainers pattern if Docker is available.
- Tests assert `401` vs `403`, refresh token rotation/reuse, inactive users, password reset, email verification, role assignment/removal, and permission assignment/removal.

### 19. Migration Plan

- Add SQLModel table models and import them into Alembic metadata registration.
- Create a new reversible migration after `20260427_0002`.
- Use PostgreSQL UUID, timezone-aware timestamps, JSONB for metadata, unique constraints, foreign keys, check constraints, and indexes.
- Do not run migrations against production automatically.
- Rollback drops auth/RBAC tables in dependency order without touching Kanban tables.

### 20. Context7 Documentation Checks

| Library | Detected/Chosen Version | Context7 ID | APIs Confirmed | Design Impact |
| --- | --- | --- | --- | --- |
| FastAPI | 0.135.3 | `/websites/fastapi_tiangolo` | `OAuth2PasswordBearer`, `Security`, `SecurityScopes`, dependency composition, `Response` cookie parameter, current `401` auth behavior | Use bearer access tokens, explicit dependencies, and `401` for invalid auth. |
| Starlette | 1.0.0 | `/kludex/starlette` | `Response.set_cookie`, `delete_cookie`, `httponly`, `secure`, `samesite`, middleware references | Refresh token stored in HttpOnly cookie with configurable secure SameSite flags. |
| SQLAlchemy | 2.0.49 | `/websites/sqlalchemy_en_20` | association tables, UUID types, indexes/constraints, PostgreSQL types | Model RBAC joins through association tables and use SQLAlchemy column constructs from SQLModel. |
| Alembic | 1.18.4 | `/websites/alembic_sqlalchemy` | `op.create_table`, `create_index`, FK/unique/check constraints, reversible migrations | New migration will be handwritten and reversible. |
| SQLModel | 0.0.38 | `/websites/sqlmodel_tiangolo` | `Field`, table models, `Session`, `select`, metadata, FastAPI compatibility | Keep sync SQLModel style rather than introducing async SQLAlchemy. |
| psycopg | 3.3.3 | `/websites/psycopg_psycopg3` | `postgresql+psycopg` compatibility, parameter binding notes, transactions | Preserve current PostgreSQL driver and avoid dynamic SQL interpolation. |
| Pydantic | 2.13.0 | `/websites/pydantic_dev_validation` | `BaseModel`, `ConfigDict(from_attributes=True)`, `model_validate` | Use Pydantic v2 schemas and ORM serialization patterns. |
| pydantic-settings | 2.13.1 | `/pydantic/pydantic-settings` | `BaseSettings`, `SettingsConfigDict`, `env_prefix`, `.env`, `extra="ignore"` | Extend existing `AppSettings` with `APP_AUTH_*` config. |
| PyJWT | chosen new dependency | `/jpadilla/pyjwt` | `jwt.encode`, `jwt.decode`, algorithms, issuer, audience, required claims, exceptions | Use PyJWT for signed access tokens with strict validation. |
| argon2-cffi | chosen new dependency | `/hynek/argon2-cffi` | `PasswordHasher`, `hash`, `verify`, `check_needs_rehash`, RFC 9106 profiles | Use Argon2id password hashes through maintained direct library. |
| pytest | 9.0.3 | `/websites/pytest_en_stable` | fixtures, parametrization, markers | Follow existing pytest marker and fixture style. |
| HTTPX | 0.28.1 | `/encode/httpx` | headers, cookies, auth client behavior | Align `TestClient` assertions for bearer headers and cookies. |

Limitations: Context7 did not resolve `pwdlib` as a library ID. FastAPI docs referenced `pwdlib`, but the implementation will use `argon2-cffi` directly because its API was confirmed by Context7.

## Risks / Trade-offs

- [Risk] Local rate limiting is process-local. -> [Mitigation] Keep it simple, configurable, and replaceable.
- [Risk] Stale access tokens could retain old roles. -> [Mitigation] Compare JWT `authz_version` against current user row on each protected request.
- [Risk] Browser cookie refresh can have CSRF exposure. -> [Mitigation] HttpOnly + SameSite + Origin check for cookie-backed refresh/logout endpoints.
- [Risk] Bootstrap admin password can leak through shell history. -> [Mitigation] CLI reads password from an environment variable, not from a positional argument.
- [Risk] Email/password reset token delivery is not implemented. -> [Mitigation] Persist internal tokens and expose raw tokens only in explicit development/test configuration; production delivery can be added later.

## Open Questions

- Which production origin list should be configured when browser clients are added?
- Which email delivery provider should consume internal password reset and email verification tokens in a future change?
- Should Kanban write endpoints eventually move from optional API key protection to RBAC permissions in a separate compatibility-aware change?
