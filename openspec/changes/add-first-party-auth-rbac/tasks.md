## 1. Inspection And Documentation

- [x] 1.1 Record detected project structure, FastAPI style, settings, PostgreSQL connection, migrations, tests, OpenSpec, Context7, admin endpoints, and tenancy in `design.md`
- [x] 1.2 Query Context7 for detected libraries and chosen new auth dependencies before implementation
- [x] 1.3 Validate OpenSpec artifacts for `add-first-party-auth-rbac` with strict validation

## 2. Dependencies And Configuration

- [x] 2.1 Add maintained JWT and Argon2 password hashing dependencies
- [x] 2.2 Extend `AppSettings` with required auth/RBAC configuration
- [x] 2.3 Update `.env.example` with auth/RBAC environment variables and no real secrets

## 3. Persistence Models And Migrations

- [x] 3.1 Add SQLModel table models for users, roles, permissions, user roles, role permissions, refresh tokens, internal tokens, and auth audit events
- [x] 3.2 Register auth SQLModel metadata with Alembic without breaking existing Kanban metadata
- [x] 3.3 Add a reversible Alembic migration for auth/RBAC tables, constraints, and indexes

## 4. Crypto, Tokens, And Rate Limiting

- [x] 4.1 Implement password hashing and verification with Argon2id
- [x] 4.2 Implement opaque token generation and hashing helpers
- [x] 4.3 Implement JWT access token encode/decode with required claims and issuer/audience validation when configured
- [x] 4.4 Implement local replaceable rate limiter for sensitive auth endpoints

## 5. Repositories And Services

- [x] 5.1 Implement sync SQLModel auth repository for users, roles, permissions, sessions, internal tokens, and audit events
- [x] 5.2 Implement auth service for registration, login, refresh rotation/reuse detection, logout, logout-all, password reset, and email verification
- [x] 5.3 Implement RBAC service for roles, permissions, user-role assignment, role-permission assignment, authz version invalidation, and auditing
- [x] 5.4 Implement seed/bootstrap command for roles, permissions, and first `super_admin`

## 6. HTTP Schemas, Dependencies, And Routers

- [x] 6.1 Add Pydantic request/response schemas for auth and RBAC without exposing secrets
- [x] 6.2 Add FastAPI dependencies for current user/principal, active users, roles, and permissions
- [x] 6.3 Add auth endpoints under `/auth`
- [x] 6.4 Add protected admin RBAC endpoints under `/admin`
- [x] 6.5 Wire auth routes and container into `src/main.py` using the existing feature composition pattern

## 7. Tests

- [x] 7.1 Add unit tests for crypto, JWT validation, token hashing, rate limiting, and permission dependency behavior
- [x] 7.2 Add e2e tests for registration, login, refresh rotation, refresh reuse, logout, logout-all, current user, inactive user, and `401` vs `403`
- [x] 7.3 Add e2e tests for role creation/update, permission creation, assigning/removing permissions to roles, assigning/removing roles to users, and audit behavior
- [x] 7.4 Add tests for password reset and email verification flows

## 8. Documentation And Validation

- [x] 8.1 Document how to seed roles/permissions and create the first `super_admin`
- [x] 8.2 Run relevant unit/e2e tests and fix failures
- [x] 8.3 Run formatting/linting or targeted checks when feasible and fix failures
- [x] 8.4 Run final OpenSpec validation and summarize files, commands, Context7 documentation, tests, and manual validation steps
