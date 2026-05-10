## Context

The template currently uses flat RBAC. Each authenticated user holds zero or more roles; each role holds zero or more permissions; each route is gated by a global `require_permissions` dependency that inspects the JWT's `roles` claim and dereferences against the seeded role/permission grid (`application/seed.py`). The model demonstrates the simplest authorization shape but is silent on resource-scoped authorization, which is what most real backends actually need ("can this user delete *this specific* board?").

Audit columns (`created_by`, `updated_by`) are populated on every kanban write but never read. Route guards live in `main.py` at mount time. The `super_admin` role is bootstrapped via env vars at startup. JWT tokens carry a `roles: [...]` claim; the principal cache invalidates on `User.authz_version` bumps triggered by role/permission changes.

This change replaces RBAC wholesale with Relationship-Based Access Control (ReBAC), modeled on Google Zanzibar / SpiceDB / OpenFGA. Because the template has no production data to migrate, removal is greenfield: the four RBAC tables, all RBAC code, and all RBAC tests are deleted in the same change that introduces ReBAC. A separate cleanup proposal will follow against the new code.

The audience for this template is engineers reading the codebase to learn how to build a hexagonal FastAPI backend. Authorization should be the most teachable surface in the project, not the least.

## Goals / Non-Goals

**Goals:**

- Demonstrate ReBAC end-to-end in a hexagonal architecture: a single `AuthorizationPort` that the application layer calls; two adapters behind that port (in-repo SQLModel engine; SpiceDB stub showing port parity); resource-scoped checks at the HTTP boundary.
- Make authorization the canonical demonstration of how kanban applies auth + authz: every read, write, and delete of a kanban resource passes through `AuthorizationPort.check`. Listing operations call `lookup_resources` so filtering happens at the authz layer, not after fetch.
- Eliminate the parallel "global permissions" path. There is one authorization model in this template, and it is ReBAC.
- Keep the existing principal-cache invalidation contract intact (`User.authz_version` bumps), so the JWT lifecycle and rate-limit story are unchanged.
- Ship the SpiceDB adapter as a structural placeholder: not runtime-functional, but byte-for-byte aligned with the port so a reader can see at a glance that swapping engines is a one-adapter change.

**Non-Goals:**

- Not building a production-grade ReBAC engine. The in-repo engine resolves hierarchy and cross-resource inheritance at check time; for high-traffic deployments, a real ReBAC system with materialized expansion is the right call. The design doc names this explicitly.
- Not preserving any RBAC-era data, code, or behavior. Greenfield removal. Downgrade exists for migration round-trip testing only — it does not preserve relationships.
- Not introducing user-defined relations or schema-driven authorization (the kind SpiceDB / OpenFGA support via a schema language). Relations and computed inheritance are coded in `application/authorization/actions.py`. This keeps the template grounded in code that's easy to read.
- Not addressing the cleanups noted in the proposal's "Out of scope" section — those land in `template-quality-cleanups` against the new code.
- Not introducing per-tenant or organization scoping. The system resource is a single global instance (`system:main`); kanban resources are global, not org-scoped.

## Decisions

### D1. AuthorizationPort shape: Zanzibar-flavored API at the application boundary

The port exposes five methods:

- `check(user_id: UUID, action: str, resource: tuple[str, str]) -> bool`
- `lookup_resources(user_id: UUID, action: str, resource_type: str) -> list[str]`
- `lookup_subjects(resource: tuple[str, str], relation: str) -> list[UUID]`
- `write_relationships(tuples: list[Relationship]) -> None`
- `delete_relationships(tuples: list[Relationship]) -> None`

**Why this shape**: It mirrors the SpiceDB / OpenFGA API surface, so a reader who learns the port can read SpiceDB's docs without retraining. It also draws the right line for hexagonal architecture: action→relation dispatch is *application* concern (it depends on the kanban domain, not the engine), but check resolution is *adapter* concern (it depends on the storage and computation strategy).

**Alternatives considered**:
- *Two layers — `RelationshipStorePort` + an in-app engine over it*. Rejected: it would mean SpiceDB users couldn't use SpiceDB's check engine, only its storage. That's the opposite of how SpiceDB is designed to be consumed.
- *A single `authorize(user, action, resource)` method with no listing*. Rejected: list endpoints (`GET /boards`) need `lookup_resources`, otherwise we'd have to fetch all boards and post-filter — bad for any non-trivial dataset and bad demonstration.

### D2. Action → relation dispatch lives in the application layer

`application/authorization/actions.py` defines the per-resource action map:

```python
KANBAN_ACTIONS: dict[str, frozenset[str]] = {
    "read":   frozenset({"reader", "writer", "owner"}),
    "update": frozenset({"writer", "owner"}),
    "delete": frozenset({"owner"}),
}

SYSTEM_ACTIONS: dict[str, frozenset[str]] = {
    "manage_users": frozenset({"admin"}),
    "read_audit":   frozenset({"admin"}),
}

ACTIONS: dict[str, dict[str, frozenset[str]]] = {
    "kanban": KANBAN_ACTIONS,
    "system": SYSTEM_ACTIONS,
}
```

**Why in the application layer**: The map is part of the *contract* between routes and the engine — both sides need to agree on it. Putting it in `application/` (not in the adapter) makes it easy to test and reuse, and it stays code, not configuration. Adapters consume it via the port. SpiceDB's adapter would translate this map into a schema once at startup.

**Alternatives considered**:
- *Schema language file (e.g., a `.zed` schema)*. Rejected as out of template scope: it adds a parser, a schema validator, and a new format to learn. Code is more grep-able and testable.
- *Inline hierarchy in the engine, no actions map*. Rejected: the route layer needs to express "this action requires writer-or-owner" without knowing about the engine.

### D3. Hierarchy and cross-resource inheritance resolved at check time

The in-repo engine resolves authorization at check time:

- **Hierarchy**: `owner ⊇ writer ⊇ reader`. When checking for `reader`, the query searches for tuples with relation in `{reader, writer, owner}`. Implementation: a small per-resource-type relation expansion map.
- **Cross-resource inheritance**: A check on `card:{id}` for `reader` walks `card.column_id → column.board_id → board:{id}`, then checks the board for `reader`. Walked synchronously inside `check`. No card or column tuples are stored.

**Why check time, not write time**:

- *Write-time expansion* is what real ReBAC engines do for performance: when a user is added as `reader` to a board, the engine writes implied tuples for every card and column on that board. That is the correct production approach but produces unbounded write amplification: adding a board reader fans out to N columns × M cards. Not a good demonstration.
- *Check time* is one more SQL query (or two — one for the resource-type-specific check, one to walk parent resources). Honest to the demonstration; the design doc names the scaling cliff.

**Trade-off acknowledged**: this won't scale past the low-millions-of-relationships range without help. The design doc says so.

### D4. The `relationships` table

Single table:

| column         | type            | notes |
|---             |---              |---    |
| `id`           | UUID PK         | |
| `resource_type`| varchar(50)     | e.g., `kanban`, `system`. |
| `resource_id`  | varchar(64)     | resource UUID or sentinel like `main`. |
| `relation`     | varchar(50)     | e.g., `owner`, `writer`, `reader`, `admin`. |
| `subject_type` | varchar(50)     | always `user` in this template; future-proofs for groupsets. |
| `subject_id`   | varchar(64)     | user UUID. |
| `created_at`   | timestamptz     | audit. |

Indexes:
- `(resource_type, resource_id, relation)` — drives `check` and `lookup_subjects`.
- `(subject_type, subject_id, resource_type, relation)` — drives `lookup_resources`.

Uniqueness: `UNIQUE (resource_type, resource_id, relation, subject_type, subject_id)` — duplicate writes are no-ops, not errors.

**Why varchar over enums**: A reader can add a new relation by editing `actions.py` and writing tuples with that relation; no schema migration required. Enum types lock that path.

**Why string subject IDs**: Future-proofs for non-user subjects (group sets, service accounts). The template doesn't use them, but a reader extending the template won't hit a wall.

### D5. The `system` resource and bootstrap

A single global instance: `(resource_type='system', resource_id='main')`. One relation: `admin`.

Bootstrap flow on startup (when `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` are both set):

1. Look up the user by email; if absent, `RegisterUser.execute(email, password)`.
2. Write the tuple `system:main#admin@user:{user_id}` (idempotent via the unique constraint).
3. Bump `User.authz_version` for that user.
4. Record audit event `authz.bootstrap_admin_assigned` (renamed from `rbac.super_admin_bootstrapped`).

**Why a sentinel `main` instead of a singleton table**: It's the same pattern Zanzibar uses — system-level relations are tuples on a well-known resource. A reader sees that "system admin" is just a relationship on a particular resource, which makes the model uniform.

### D6. JWT token shape changes

Drop the `roles` claim from issuance and decode. Token claims are now: `sub`, `exp`, `iat`, `nbf`, `jti`, `authz_version`.

**Why drop**: Roles don't exist anymore. Carrying a stale `roles: []` claim teaches confusion. Authorization checks always go through `AuthorizationPort.check`, which consults the relationships store directly. The principal cache (still keyed by `(user_id, authz_version)`) absorbs the per-request cost.

**Trade-off**: Every authz check is one more cache lookup (and on miss, one DB query for hierarchy + N walks for cross-resource). Acceptable for a template; the cache keeps it cheap in practice.

### D7. Route gating via `require_authorization`

New platform dependency: `platform/api/authorization.py:require_authorization(action: str, resource_type: str, id_loader: Callable[[Request], str] | None = None)`. Behavior:

- If `id_loader` is `None`, treat the resource as the singleton `(resource_type, "main")` — used for system-level routes.
- Otherwise call `id_loader(request)` to resolve the resource id from path params.
- Resolve the current principal (existing dependency).
- Call `auth.check(user_id, action, (resource_type, resource_id))`.
- On deny, raise `HTTPException(403, "Permission denied")`.

Route examples:

- `POST /boards` — *no* dependency. The use case writes the owner tuple after persisting the board.
- `GET /boards` — *no* dependency. The use case calls `lookup_resources` to filter.
- `GET/PATCH/DELETE /boards/{board_id}` — `require_authorization("read"|"update"|"delete", "kanban", lambda r: r.path_params["board_id"])`.
- `POST /boards/{board_id}/columns`, `DELETE /columns/{column_id}` — check on the parent board. Column delete needs a column→board lookup (lives in the platform helper).
- `POST /columns/{column_id}/cards`, `PATCH /cards/{card_id}`, `GET /cards/{card_id}` — check via card→column→board chain.
- `GET /admin/users`, `GET /admin/audit-log` — `require_authorization("manage_users", "system", None)` and `require_authorization("read_audit", "system", None)`.

**Why ID loaders not field paths**: the loader is a one-line lambda; explicit beats magic. Readers see exactly how the id is extracted.

### D8. Cache invalidation: keep the existing contract

Every `write_relationships` and `delete_relationships` call that affects a user (i.e., the subject is a user UUID) bumps `User.authz_version`. The principal cache invalidation contract is untouched.

**Trade-off acknowledged**: a single relationship change for user U revokes *all* of U's access tokens, even tokens unrelated to the resource that changed. This is the same UX as today (a role change today bumps `authz_version` for every user with that role). Per-resource cache granularity is a future optimization; the design doc names it.

### D9. Adapter layout

```
src/features/auth/
  application/
    authorization/
      __init__.py
      ports.py                     # AuthorizationPort
      actions.py                   # ACTIONS map
      errors.py                    # NotAuthorizedError
      hierarchy.py                 # relation expansion (owner→{owner,writer,reader})
      resource_graph.py            # parent-resource walk: card→column→board
  adapters/outbound/
    authorization/
      __init__.py
      sqlmodel/
        __init__.py
        models.py                  # RelationshipTable
        repository.py              # SQLModel-backed AuthorizationPort
      spicedb/
        __init__.py
        README.md                  # explains the swap and why this is a stub
        adapter.py                 # AuthorizationPort skeleton, NotImplementedError
```

**Why `auth` owns it**: ReBAC is part of the auth feature's bounded context; bootstrapping, audit events, and `User.authz_version` already live there. Splitting into a third feature would create import-linter trouble (kanban can't depend on a third feature) and would fragment the demonstration.

**Trade-off**: kanban now reads (indirectly, via the port) authz state owned by auth. But it always did — `require_permissions` already lived in the platform layer and consumed the auth-feature's `Principal`. The port makes that dependency explicit.

### D10. SpiceDB stub: structural placeholder, not runtime

`adapters/outbound/authorization/spicedb/adapter.py` defines `SpiceDBAuthorizationAdapter(AuthorizationPort)` with the same five methods, each raising `NotImplementedError("SpiceDB integration is a stub; see README.md for the schema and the API mapping")`. The README states which SpiceDB API maps to which port method (`CheckPermission` → `check`, `LookupResources` → `lookup_resources`, etc.), and shows the equivalent `.zed` schema for the kanban + system relations.

**Why ship a non-runtime stub**: it teaches that the port is a *real* abstraction, not just renaming. Marked with `# pragma: no cover` so the test suite doesn't count it.

## Risks / Trade-offs

[Risk] Greenfield removal of RBAC in one change is a wide blast radius — 4 tables dropped, 13+ files deleted, JWT shape changes.
→ Mitigation: This is a template, not a production system. The migration's downgrade restores empty RBAC tables for round-trip testing, but no project running on this template has data to lose. The change is also gated by a single Alembic revision, so a rollback is one `alembic downgrade -1`.

[Risk] Check-time hierarchy and cross-resource inheritance won't scale to large datasets — `lookup_resources` returning thousands of board IDs becomes expensive, and per-card checks walk the parent chain.
→ Mitigation: Document explicitly in `design.md` and in the in-repo adapter's module docstring. Provide a comment block showing what materialized expansion would look like and when to switch.

[Risk] Aggressive `authz_version` bumps mean a single board ownership change revokes the user's access tokens for unrelated resources.
→ Mitigation: Document. This matches today's RBAC behavior (role changes already do this). Future per-resource cache granularity is a follow-up. Keep the principal cache TTL short (default 5s) so worst-case lag is bounded.

[Risk] Two patterns are only consistent if `bootstrap_super_admin` actually writes the tuple (no fallbacks).
→ Mitigation: Make the bootstrap test assert *zero* RBAC tables exist (CI guard) and *one* `system:main#admin@user:...` tuple exists.

[Risk] Listing-with-authz can leak count information ("I got 0 results" reveals "I have no access to anything"). Less of a security risk in this template; worth noting.
→ Mitigation: Out of scope for this change. Document for future work.

[Risk] Renaming the audit event from `rbac.super_admin_bootstrapped` to `authz.bootstrap_admin_assigned` could surprise consumers of the audit log.
→ Mitigation: There are no production consumers of this template's audit log. Mention in the proposal's BREAKING markers.

## Migration Plan

1. **Pre-merge**: branch from main with this change. Run the migration locally and confirm `make ci` passes.
2. **Single Alembic migration** drops `roles`, `permissions`, `role_permissions`, `user_roles` and creates `relationships`. Downgrade reverses the schema; no data preservation (template).
3. **Code merge**: deletes RBAC code and adds ReBAC code in the same commit/PR so the template is never in a half-state.
4. **Bootstrap on first start**: existing `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_*` env vars now seed a system-admin tuple instead of assigning a role. Operationally identical from outside.
5. **Rollback**: `alembic downgrade -1` + revert the merge. No data to restore.

## Open Questions

- Should `system:main` be created automatically on the first bootstrap, or always exist as a baseline row in the `relationships` table? *Resolved during design*: it's a sentinel resource id, no row needs to exist for the resource itself; only `admin` tuples on it are stored.
- Should the SpiceDB adapter README include a runnable example with `docker-compose -f docker-compose.spicedb.yml`? *Decision*: out of scope for this change; mention as a follow-up. The stub is structural only.
- Should `lookup_resources` paginate? *Decision*: yes, with a `limit` parameter (default 100, max 500), mirroring existing admin endpoints. Documented in the spec.
