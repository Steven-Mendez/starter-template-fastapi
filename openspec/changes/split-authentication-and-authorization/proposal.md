## Why

Authentication and authorization are different concerns with different change cadences. Authentication answers "who are you?" — passwords, JWTs, refresh tokens, sessions, MFA, OAuth. Authorization answers "what can you do?" — relationships, policies, ReBAC engine, action registries. The first changes rarely. The second changes often as the product grows.

Today both live inside `features/auth/`. After the `decouple-authz-from-features` change, the authorization engine no longer hardcodes other features — but it still sits *inside* the auth slice. For a starter template the message that delivers is: "authorization is a sub-concern of authentication." That's pedagogically wrong. ReBAC works just as well without any login system, and a real password-based auth feature works just as well without ReBAC.

This change lifts authorization into its own feature slice, with the relationships table owned by the platform layer (cross-feature data) and `User.authz_version` invalidation routed through a small port that auth implements. The result: three independent features (`auth`, `authorization`, `kanban`) communicating only through ports, which is the canonical demonstration of hexagonal architecture this template is supposed to teach.

## What Changes

- **BREAKING (internal layout)** Introduce a new feature slice `src/features/authorization/` containing the AuthorizationPort, the ReBAC engine, the action registry, and the `bootstrap_system_admin` use case. Move all corresponding code out of `src/features/auth/`.
- **BREAKING (data ownership)** Move the `relationships` SQLModel table and its migrations into the platform layer at `src/platform/persistence/sqlmodel/authorization/`. The schema becomes platform-owned; the authorization feature reads/writes it through an adapter.
- **BREAKING (internal API)** The authorization feature SHALL NOT import from `features/auth/`. Cache invalidation flows through a new `UserAuthzVersionPort` defined in `features/authorization/application/ports/outbound/`. Auth implements the port via a thin adapter that bumps `users.authz_version`.
- Move `bootstrap_system_admin` to the authorization feature (it operates on the relationships table and the registry, not on auth-specific concerns). Auth keeps `register_user`, `login`, `refresh`, `logout`, password-reset, and email-verify.
- Move `BootstrapSystemAdmin`'s dependency on `RegisterUser` behind a small `UserRegistrarPort` that auth implements. Authorization never imports the auth feature directly.
- Move admin HTTP routes (`/admin/users`, `/admin/audit-log`) to wherever the underlying use case lives: `list_users` and `list_audit_events` stay in auth (they list auth's own state); their `require_authorization` dependency continues to gate them on `system:main` via the platform-level dependency.
- Update Import Linter contracts: `auth → authorization` not allowed; `authorization → auth` not allowed; both → platform allowed; kanban → authorization allowed; kanban → auth not allowed (kanban resolves the principal via the platform-level resolver, same as today).
- Update CLAUDE.md to document three features and their boundaries; document the new `UserAuthzVersionPort` and `UserRegistrarPort` seams.
- Update Alembic: add a migration that does **no** schema change but logically transfers ownership (the table moves modules; the SQL is untouched). Document the move in a comment.
- Add a contract test that asserts the layering: `import_linter` must pass and a unit test must verify that no module under `features/auth/` references `features/authorization/` (and vice versa) outside of explicit port adapters.

## Capabilities

### New Capabilities

- `authentication`: Identity-only capability covering register/login/refresh/logout, password reset, email verify, JWT issuance and decoding, and the `User`/`refresh_token`/`internal_token`/`auth_audit_event` schema. Spec extracted from the existing implicit auth surface; no new behavior.

### Modified Capabilities

- `authorization`: ownership boundary moves into a dedicated feature slice. The capability's external behavior is unchanged (same port, same wire format, same hierarchy and parent walks). The spec gains requirements about layering: who owns what code, who owns what tables, and how cache invalidation flows through ports.

## Impact

- **`src/features/authorization/`** (new): owns the `AuthorizationPort` Protocol, `AuthorizationRegistry`, the SQLModel adapter, the SpiceDB stub, and `BootstrapSystemAdmin`. Its `composition/` produces an `AuthorizationContainer` exposing the port and the registry.
- **`src/features/auth/`**: shrinks to authentication concerns only. Loses `application/authorization/`, `adapters/outbound/authorization/`, and the `BootstrapSystemAdmin` use case. Gains a small `UserAuthzVersionAdapter` (implements the new port) and `UserRegistrarAdapter` (implements the new port).
- **`src/platform/persistence/sqlmodel/`**: new module hosting the `RelationshipTable` SQLModel and its Alembic migration helper. Cross-feature data lives here.
- **`src/main.py`**: lifespan now builds `auth → authorization → kanban`, wiring `UserAuthzVersionPort` and `UserRegistrarPort` from auth into authorization, and the kanban-side parent walk into authorization's registry.
- **`src/platform/api/authorization.py`**: `require_authorization` continues to read `app.state.authorization`. The platform layer was already feature-agnostic; only the import path of the port changes.
- **Tests**: split into `src/features/auth/tests/`, `src/features/authorization/tests/`, and `src/features/kanban/tests/`. The cross-feature contract test moves to `src/platform/tests/test_authorization_layering.py`.
- **Import Linter contracts** in `pyproject.toml`: explicit forbids on `auth → authorization` and `authorization → auth`; allow both → `platform`.
- **Out of scope**: changing the wire format, adding new auth methods (OAuth, magic-link), introducing event-based invalidation, or implementing the SpiceDB adapter. Those are independent follow-ups.
- **Depends on**: `decouple-authz-from-features` MUST land first. This proposal assumes the registry exists and that auth's authorization layer no longer mentions kanban.
