## Why

The service currently exposes Kanban resources protected only by an optional write API key and has no first-party user authentication, session management, or persistent authorization model. This change adds professional in-app authentication and RBAC so administrative and future protected resources can enforce least privilege without relying on external identity providers.

## Problem

- There is no persisted user model, credential flow, session revocation, password reset, email verification, or audit trail.
- Authorization is not modeled as durable roles and permissions in PostgreSQL.
- Administrative capabilities need explicit permission checks with correct `401` unauthenticated and `403` unauthorized behavior.

## Objectives

- Add first-party authentication with Argon2id password hashing, short-lived JWT access tokens, opaque rotating refresh tokens, and secure cookie handling.
- Add persistent RBAC in PostgreSQL with roles, permissions, user-role assignments, role-permission assignments, constraints, indexes, and audit events.
- Provide protected auth and admin RBAC endpoints without breaking existing Kanban endpoints or the current optional write API key behavior.
- Follow OpenSpec spec-driven design: proposal, design, formal specs, executable tasks, validation, then implementation.
- Use Context7 documentation checks for current library APIs before designing and implementing.

## Non-Objectives

- No Firebase, Auth0, Clerk, Supabase Auth, Cognito, OAuth provider integration, Redis, Celery, or external rate-limiting service.
- No ABAC/PBAC policy engine in this phase.
- No replacement of the current feature-first hexagonal structure, SQLModel persistence style, Alembic setup, or Kanban API behavior.
- No long-lived JWT-only sessions, plaintext refresh tokens, reversible password encryption, or `admin=true` authorization shortcuts.

## What Changes

- Add a new `auth` feature mounted alongside Kanban and wired through `src/main.py` using the existing route-mount/lifespan-container pattern.
- Add PostgreSQL tables for `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `refresh_tokens`, `auth_audit_events`, and internal auth tokens.
- Add auth endpoints for registration, login, refresh, logout, logout-all, current user, password reset, and email verification.
- Add admin RBAC endpoints for managing roles, permissions, role-permission links, and user-role links.
- Add FastAPI dependencies for current principal resolution, active-user enforcement, role checks, and permission checks.
- Add a safe management command to seed roles/permissions and create the first `super_admin` outside public registration.
- Add local, replaceable in-memory rate limiting for sensitive auth endpoints.
- Add `.env.example` entries for required auth configuration without committing real secrets.
- Add tests for authentication flows, refresh rotation/reuse, inactive users, RBAC authorization, `401` vs `403`, admin mutations, password reset, and email verification.

## Capabilities

### New Capabilities

- `auth`: First-party authentication, sessions, token lifecycle, password reset, email verification, audit, rate limiting, and secure configuration.
- `rbac`: Persistent role-based access control with roles, permissions, authorization dependencies, admin RBAC endpoints, least privilege, and audit events.

### Modified Capabilities

- None. Existing Kanban and platform behavior remains compatible; new protection applies to new auth/RBAC endpoints unless explicitly changed later.

## Scope

- Backend-only FastAPI implementation using the detected PostgreSQL/SQLModel/Alembic stack.
- Sync SQLModel repositories to match the current codebase; SQLAlchemy 2.x Core/Alembic constructs are used where SQLModel delegates to SQLAlchemy.
- JWT access tokens returned in JSON and accepted through `Authorization: Bearer`.
- Opaque refresh tokens stored only as hashes in PostgreSQL and sent by default as HttpOnly cookies.

## Risks

- Auth introduces sensitive flows; implementation must avoid logging passwords, tokens, full hashes, or secrets.
- Cookie refresh flows need secure production defaults while remaining usable in local development through explicit settings.
- RBAC changes must invalidate or obsolete prior access tokens through `authz_version` to avoid stale permissions.
- Local in-memory rate limiting is process-local and suitable only as an initial replaceable guard.

## Plan de Migracion

- Add a reversible Alembic migration after the existing Kanban migrations.
- Do not apply production migrations automatically.
- Provide a seed/management command for initial roles, permissions, and first `super_admin` creation.
- Keep new tables independent from Kanban tables, so rollback does not alter existing Kanban data.

## Criterios de Aceptacion

- OpenSpec validates strictly for `add-first-party-auth-rbac`.
- Auth endpoints implement registration, login, refresh rotation, logout, logout-all, current user, password reset, and email verification.
- RBAC admin endpoints are protected by explicit permissions and return `401` for missing/invalid auth and `403` for insufficient permissions.
- Refresh token reuse detection revokes the token family.
- Roles and permissions persist in PostgreSQL with normalized unique names, constraints, indexes, active flags, and audit events.
- New users receive only the configured default non-admin role when it exists.
- Tests cover success and failure paths requested in the change.

## Methodology Dependencies

- OpenSpec governs the workflow and artifacts for spec-driven design.
- Context7 provides current library documentation checks before design and implementation; it does not replace OpenSpec.

## Authorization Decision

The principal authorization model is persistent RBAC with explicit roles and permissions stored in PostgreSQL. Roles never imply broad power by name alone; access decisions use explicit permissions such as `users:read`, `roles:manage`, `permissions:manage`, `auth:sessions:revoke`, and `admin:access`.

## Impact

- Affected code: `src/main.py`, platform settings, new `src/features/auth/**`, Alembic metadata imports, new migration, tests, `.env.example`, and documentation.
- Affected APIs: new `/auth/*` and `/admin/*` routes only.
- Dependencies: add maintained JWT and Argon2 password hashing libraries after Context7 checks.
- Systems: PostgreSQL schema gains auth/RBAC tables; no external services are introduced.
