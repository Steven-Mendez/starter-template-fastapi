## Context

After `decouple-authz-from-features` lands, `features/auth/application/authorization/` is feature-agnostic but still lives inside the auth slice. This change lifts it into its own feature slice and moves the cross-feature `relationships` table into platform-owned persistence.

The motivation is pedagogical: a starter template that ships three features (`auth`, `authorization`, `kanban`) talking through ports is a much stronger demonstration of hexagonal architecture than two features where one bundles the other. The template should be the kind of layout a reader copies into a real project — and in a real project, authentication and authorization belong in different bounded contexts.

There's a real engineering benefit too: if the project grows OAuth, magic-link, or MFA, those changes touch only the auth slice. If it grows new resource types or migrates to SpiceDB, those changes touch only the authorization slice. The two evolve independently.

## Goals / Non-Goals

**Goals:**

- Three independent feature slices: `auth`, `authorization`, `kanban`. Import-linter enforces that none import from another except through platform-level Protocols.
- The `relationships` table and the `User.authz_version` mechanism are explicitly cross-feature data, owned by platform/persistence. Each feature reads/writes through its own adapter.
- Cache invalidation contract preserved: every relationship write affecting user U bumps `User.authz_version`. The mechanism is now a port: authorization calls `UserAuthzVersionPort.bump(user_id)`, auth implements it.
- Bootstrap of the first system admin moves to the authorization feature: it's an authz operation that happens to need a user, so authorization depends on `UserRegistrarPort` (auth implements).
- HTTP behavior, JWT format, relationship tuple format, and database schema are all unchanged.
- CLAUDE.md describes the three-feature layout clearly enough that a reader knows where to add a new feature.

**Non-Goals:**

- Changing any user-visible behavior (HTTP, JWT, audit events, error responses).
- Changing the database schema. The migration is "metadata-only" — table ownership shifts but the DDL is identical.
- Introducing an event bus or message queue. The `UserAuthzVersionPort` is a synchronous in-process call; that's the simplest hex-clean mechanism.
- Implementing the SpiceDB adapter. The stub stays a stub.
- OAuth, MFA, or any new authentication method.
- Splitting `kanban` further or refactoring its internals.

## Decisions

### D1. Three feature slices with a strict no-cross-import rule

```
src/
  platform/
    persistence/sqlmodel/authorization/
      models.py         # RelationshipTable
      migrations/...    # owns the relationships-table migration history going forward
  features/
    auth/               # authentication only: User, JWT, refresh, password reset
    authorization/      # AuthorizationPort, registry, engine, bootstrap
    kanban/             # uses authorization via port; uses platform principal resolution
```

`features/auth/` and `features/authorization/` SHALL NOT import from each other. They communicate only through Protocols defined either in `platform/shared/` or in the consumer's own `application/ports/outbound/`.

**Why this layout**: it forces the right dependencies. Auth knows about users; authorization knows about access control; neither depends on the other's domain.

**Alternative considered**: one shared "identity" feature that includes both. Rejected because the whole point of this change is to teach that they're different bounded contexts.

### D2. Platform owns the relationships table

The `RelationshipTable` SQLModel and its Alembic migration ownership move to `src/platform/persistence/sqlmodel/authorization/`. The authorization feature has an adapter that reads/writes through this table, but the table definition is platform code.

**Why platform**: the table is referenced by every feature's authz checks at request time. It's the same shape of "shared infrastructure" that the `users` table arguably is — except `users` is auth-private (only auth touches it directly) whereas `relationships` is shared by every feature that authorizes anything. Platform is the right owner for the *table*, even if the *application logic* lives in the authorization feature.

**Trade-off acknowledged**: this turns platform into a slightly larger surface than a pure "infra-only" layer. The mitigation is that platform never imports from any feature, and the table only gets columns when there's a clear cross-feature use case. The `users` table stays in auth; only the explicitly-cross-feature `relationships` table moves to platform.

**Alternative considered**: keeping the table in the authorization feature. Rejected because then auth's adapter for `UserAuthzVersionPort` would need authorization-feature schema knowledge to bump the column on the user — but `users.authz_version` is auth's column. The platform-owned `relationships` keeps the data ownership story symmetric: each feature owns its own tables; platform owns truly cross-feature ones.

### D3. Cache invalidation via UserAuthzVersionPort

The current code has authorization's adapter directly bumping `users.authz_version` because the SQLModel adapter has access to the same engine as the `users` table. After the split, that's a layering violation.

New seam:

```python
# features/authorization/application/ports/outbound/user_authz_version_port.py
class UserAuthzVersionPort(Protocol):
    def bump(self, user_id: UUID) -> None: ...
```

```python
# features/auth/adapters/outbound/authz_version/sqlmodel.py
class SQLModelUserAuthzVersionAdapter:
    """Increments users.authz_version. Implements UserAuthzVersionPort."""
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
    def bump(self, user_id: UUID) -> None:
        ...  # UPDATE users SET authz_version = authz_version + 1, updated_at = now() WHERE id = :id
```

Composition root in `main.py` wires the auth adapter into the authorization container.

**Why a port, not events**: synchronous, simple, no infrastructure. An event bus would add a layer with no marginal benefit at this scale.

**Why not let authorization keep direct access**: because the whole point of the split is that authorization doesn't know about the `users` table.

**Trade-off**: extra indirection. Authorization's `write_relationships` now goes through one port call to bump the version. Negligible overhead; the bump is in the same DB transaction as the relationship write because both adapters take the same SQLAlchemy session at the UoW boundary (via session-scoped variants).

### D4. Bootstrap moves to authorization, registers via UserRegistrarPort

`BootstrapSystemAdmin` operates on the relationships table — it writes `system:main#admin@user:{id}`. That's an authz operation. The fact that it also needs to ensure the user exists is incidental.

After the split:

```python
# features/authorization/application/ports/outbound/user_registrar_port.py
class UserRegistrarPort(Protocol):
    def register_or_lookup(self, *, email: str, password: str) -> UUID: ...
```

Auth implements `UserRegistrarPort` by composing `RegisterUser` and the user repository. Authorization's `BootstrapSystemAdmin` calls the port, gets a user_id, writes the tuple, calls `UserAuthzVersionPort.bump`.

**Why the port over a bigger contract**: the bootstrap only needs "give me a user_id for this email, creating the user if necessary." That's a small surface. The port stays narrow; auth keeps `RegisterUser` as a domain use case for its own HTTP routes.

### D5. Admin routes stay in auth

`GET /admin/users` and `GET /admin/audit-log` list auth-feature data (users, auth audit events). Their use cases (`ListUsers`, `ListAuditEvents`) stay in auth.

The `require_authorization("manage_users", "system", None)` dependency on those routes is platform-level code, not feature code; it stays where it is. It calls `app.state.authorization.check(...)` which now resolves to the authorization feature's container — the only difference from today is the import path inside that container.

### D6. Database migration is metadata-only

The `relationships` table doesn't physically change. Alembic doesn't care which Python module declares the SQLModel — it tracks DDL state. The migration shipped with this change is empty:

```python
def upgrade() -> None:
    """No schema change. Ownership of relationships moves from
    src/features/auth/adapters/.../models.py to
    src/platform/persistence/sqlmodel/authorization/models.py.
    The DDL is unchanged; this revision exists to anchor the move
    in migration history.
    """
    pass

def downgrade() -> None:
    pass
```

**Why an empty migration instead of nothing**: future Alembic autogenerates against `target_metadata`. By anchoring the no-op now, the next autogenerate is clean. Also useful as documentation for anyone reviewing the migration log.

### D7. Layering enforced by Import Linter

Add three new contracts in `pyproject.toml`:

```toml
[[tool.importlinter.contracts]]
name = "Auth and authorization are independent features"
type = "forbidden"
source_modules = ["src.features.auth"]
forbidden_modules = ["src.features.authorization"]

[[tool.importlinter.contracts]]
name = "Authorization does not import from auth"
type = "forbidden"
source_modules = ["src.features.authorization"]
forbidden_modules = ["src.features.auth"]

[[tool.importlinter.contracts]]
name = "Kanban does not import from auth (only authorization is allowed)"
type = "forbidden"
source_modules = ["src.features.kanban"]
forbidden_modules = ["src.features.auth"]
```

These run as part of `make lint-arch`. Together with the existing layered contracts, this guarantees that the three features stay independent at the import level.

## Risks / Trade-offs

[Risk] Two features sharing the `users` table indirectly (auth owns it; authorization writes via port) is awkward to reason about.
→ Mitigation: explicit port + adapter. The auth-owned `SQLModelUserAuthzVersionAdapter` is one method, four lines, easy to audit. The contract in spec form is explicit.

[Risk] The composition root grows. `main.py` now wires three feature containers and four ports between them.
→ Mitigation: composition is the place where it's *supposed* to grow. That's where the architecture is most visible. Adding a small `compose.py` module is fine if `main.py` becomes uncomfortable.

[Risk] Tests that previously assumed auth-owned authorization break — fixtures need updating.
→ Mitigation: the test rewiring is mechanical (fixture renames, port stubs). Same as the test phase of the rebac-authorization change. Plan ~10–15 fixture files updated.

[Risk] Platform now owns a domain-shaped table (`relationships`).
→ Mitigation: the table only contains cross-feature authz tuples — that's exactly what platform infrastructure is. CLAUDE.md documents the rule: "Platform owns tables only when no single feature is the natural home."

[Risk] Adding a third feature to a fork of this template requires the fork's author to wire the new feature into authorization's registry from `main.py`.
→ Mitigation: that's the desired behavior. Wiring is one line; the template's CLAUDE.md and a short example in the SpiceDB README walk through it.

## Migration Plan

This is a structural refactor; the database migration is a no-op. Code merge plan:

1. **Pre-condition**: `decouple-authz-from-features` has landed.
2. Create `src/features/authorization/` skeleton (composition + application + adapters dirs).
3. Move source files from `src/features/auth/application/authorization/` and `src/features/auth/adapters/outbound/authorization/` into the new feature, updating imports.
4. Move `RelationshipTable` SQLModel and its conftest schema list into `src/platform/persistence/sqlmodel/authorization/`. Update everything that imports it.
5. Move `BootstrapSystemAdmin` use case into the new feature. Define `UserRegistrarPort` and `UserAuthzVersionPort` in authorization's `ports/outbound/`.
6. Implement the two ports in auth (`adapters/outbound/authz_version/sqlmodel.py`, `adapters/outbound/user_registrar/sqlmodel.py`).
7. Update auth's `composition/container.py` to construct the port adapters and expose them.
8. Add `authorization/composition/container.py` and `authorization/composition/wiring.py`. The container takes the two ports and produces the `AuthorizationContainer` exposing the port + registry + bootstrap.
9. Update `main.py` lifespan: build auth → build authorization (passing auth's port adapters) → register kanban (against authorization's registry) → seal registry.
10. Update Import Linter contracts. Run `make lint-arch` until green.
11. Migrate test fixtures: split into per-feature trees, rewire to the new container structure.
12. Run full quality + test suite. No external behavior changes.
13. Add the empty Alembic migration anchoring the table move.
14. Update CLAUDE.md to describe three features.

Rollback: revert the merge. No data to restore.

## Open Questions

- Should `auth.audit_events` be moved alongside the relationships table, since some events are about authz changes? *No — they're written from auth's flows (login, register, password reset) and the authz events that come from `BootstrapSystemAdmin` are a small minority. Keep audit in auth; authorization writes its events via a small `AuditPort` that auth implements.* — *Decision recorded; the proposal includes adding a small `AuditPort` in authorization's outbound ports.*
- Should the JWT issuance also move to a port? *No, it's auth-internal; authorization never issues tokens.*
- Should there be an `authorization` admin surface (e.g., `GET /admin/relationships`)? *Out of scope; useful but a separate proposal.*
