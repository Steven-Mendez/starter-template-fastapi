## Context

The current authorization engine lives at `src/features/auth/application/authorization/` and works correctly. The problem is internal: its action map, relation hierarchy, and parent-walk Protocol all speak kanban. A reader picking up the template to add a second feature has to edit three files inside auth to register the new feature's authz config — and copying that pattern into a fork compounds the coupling each time.

This change replaces the hardcoded maps with a runtime registry. Auth ships only the `system` entries (because the `system:main#admin` tuple is part of bootstrap, which is auth's concern). Every other feature registers its actions, hierarchy, and parent-walk callable from its own composition root.

The change preserves the existing public API (`AuthorizationPort` is unchanged), the wire format (relationship tuples), and the storage layer (one `relationships` table). Only the engine's *internal* contract — how it learns what actions and resources exist — moves.

## Goals / Non-Goals

**Goals:**

- Auth's `application/authorization/` no longer references any kanban term. Greppable check: no string `"kanban"`, `"column"`, `"card"` in any file under that package.
- Adding a second feature requires editing only that feature's composition wiring; no auth file changes.
- The registration API is small enough that a reader can understand it from the function signatures alone.
- Multi-level parent walks (card → column → board) work naturally through the registry instead of being a hardcoded branch in `check()`.
- Existing tests for hierarchy and inheritance keep passing with minimal rewiring; new registry tests are added.

**Non-Goals:**

- Splitting authorization into its own feature slice. That's the follow-up proposal.
- Changing the wire format (HTTP, JWT, relationships table layout).
- Changing the SpiceDB stub from a structural placeholder to runnable.
- Performance changes — the registry is a dict lookup, no measurable difference from the current constant-table read.
- A schema-file format (yaml, .zed). Decisions D1 and D2 below explain why programmatic registration wins for a template.

## Decisions

### D1. Registration is programmatic, called from each feature's composition root

Each feature owns a function that calls into the registry:

```python
# kanban/composition/wiring.py (excerpt)
def register_kanban_authorization(registry: AuthorizationRegistry, lookup: KanbanLookupRepositoryPort) -> None:
    registry.register_resource_type(
        "kanban",
        actions={
            "read":   {"reader", "writer", "owner"},
            "update": {"writer", "owner"},
            "delete": {"owner"},
        },
        hierarchy={
            "reader": {"reader", "writer", "owner"},
            "writer": {"writer", "owner"},
            "owner":  {"owner"},
        },
    )
    registry.register_parent(
        "column",
        parent_of=lambda column_id: ("kanban", lookup.find_board_id_by_column(column_id)),
        actions=...,        # column inherits kanban's actions/hierarchy by alias
    )
    # ditto for "card" pointing to "column"
```

**Why programmatic, not a schema file**: a template that's ~5k lines of Python doesn't need a parser. Composition roots are already where features wire themselves; this is one more line in the place readers expect.

**Why composition-time, not decorator-based**: decorators on use cases bind authz config to the use case, but actions+hierarchy belong to the *resource type*, not the use case. Decorators would scatter the action map across every file. Greppability is a teaching value here.

**Alternative considered**: a single `actions.yaml` per feature loaded by the registry. Rejected for the same parser-cost reason; also forces a lookup-then-execute split that complicates errors at startup.

### D2. The registry is the only seam between features and the engine

Auth exposes one new object on its container: `AuthorizationRegistry`. Features mutate it at startup; the engine reads from it on every `check`/`lookup_resources`. There is no other way to extend the engine.

```python
class AuthorizationRegistry:
    def register_resource_type(
        self,
        resource_type: str,
        *,
        actions: dict[str, frozenset[str]],
        hierarchy: dict[str, frozenset[str]],
    ) -> None: ...

    def register_parent(
        self,
        resource_type: str,
        *,
        parent_of: Callable[[str], tuple[str, str] | None],
        inherits_from: str,
    ) -> None: ...

    # Read API used by the engine
    def relations_for(self, resource_type: str, action: str) -> frozenset[str]: ...
    def expand_relations(self, resource_type: str, relations: frozenset[str]) -> frozenset[str]: ...
    def parent_of(self, resource_type: str, resource_id: str) -> tuple[str, str] | None: ...
```

**Why two register methods**: a "leaf" resource (e.g., `kanban` with stored tuples) declares actions+hierarchy. An "inherited" resource (e.g., `card` that walks to `kanban`) declares parentage and inherits the parent's actions/hierarchy by alias. This separation makes the two roles explicit instead of overloading one register.

**Inheriting actions and hierarchy from the parent type**: `register_parent("card", inherits_from="column")` means "card's actions and hierarchy are whatever column has". The walker chains until it hits a leaf type. Multi-level walks (card → column → board) just work; no special-case logic in `check()`.

### D3. Auth pre-registers only the `system` resource type

The `system` resource is part of auth's own surface — `system:main#admin` gates `/admin/users` and `/admin/audit-log`. So auth's container constructs the registry pre-populated with:

```python
registry.register_resource_type(
    "system",
    actions={"manage_users": {"admin"}, "read_audit": {"admin"}},
    hierarchy={"admin": {"admin"}},
)
```

That's the *only* thing auth registers about itself. Every other resource is registered by some other feature.

**Why this isn't "auth still knows kanban"**: it doesn't. Auth knows `system`, which is auth's own concept. Kanban's vocabulary stays in kanban.

### D4. The engine's `check()` is rewritten to walk via the registry

Today:

```python
if resource_type in {"card", "column"}:
    board_id = self._resolve_to_board(resource_type, resource_id)
    ...
if resource_type == "kanban":
    return self._check_kanban(...)
expanded = expand_relations(resource_type, required)
...
```

After the change:

```python
# Walk parents until we hit a leaf type (one with stored tuples).
walked_type, walked_id = resource_type, resource_id
while not self._registry.has_stored_relations(walked_type):
    parent = self._registry.parent_of(walked_type, walked_id)
    if parent is None:
        return False
    walked_type, walked_id = parent
required = self._registry.relations_for(resource_type, action)
expanded = self._registry.expand_relations(walked_type, required)
return self._exists_relation(session, walked_type, walked_id, expanded, user_id)
```

The check uses *the original action's* required relations (so `update` on a card still resolves to `writer/owner`) but expands and queries against *the parent's* hierarchy (so we look for `kanban#writer` tuples, not `card#writer`).

**Why the walk is iterative, not recursive**: easier to bound and easier to read; matches Zanzibar's "userset rewrite" mental model better than recursion.

### D5. Backwards compatibility for tests

Tests that previously imported constants like `KANBAN_RELATION_HIERARCHY` get rewritten to register their config against a registry fixture. A small helper `make_test_registry()` returns a registry pre-populated with the kanban + system config so most tests don't have to know about the change.

```python
@pytest.fixture
def registry() -> AuthorizationRegistry:
    return make_test_registry()
```

This keeps test churn proportional to actual coverage rather than touching every file that mentions kanban actions.

### D6. SpiceDB stub README updates

The stub adapter doesn't change behaviorally. But its README now describes the registration model: "If you replace this stub with a real SpiceDB adapter, the registry calls translate to a `.zed` schema you upload at startup; the rest of the application is unchanged." The example schema fragment stays.

## Risks / Trade-offs

[Risk] A feature forgets to register its resource types and the engine returns 403 silently for everything that feature exposes.
→ Mitigation: every `check()` for an unregistered resource type raises `UnknownActionError`, which the HTTP layer maps to 500 (not 403) so the bug surfaces during integration testing rather than as a silent denial. The existing `UnknownActionError` already does this.

[Risk] Registration order matters if two features register the same resource type.
→ Mitigation: `register_resource_type` raises if the type already exists. Forces explicit decisions at composition rather than silent overrides.

[Risk] The registry is mutable at runtime. Misuse could cause inconsistent state mid-request.
→ Mitigation: registration is allowed only before the registry's `seal()` method is called, which `main.py` invokes after wiring all features. Post-seal mutations raise. Tests can use a non-sealed registry.

[Risk] Multi-level walks compound query cost: a card check now does two lookups (card→column, column→board) before the SQL query.
→ Mitigation: existing behavior already has this cost — the only difference is that it's now driven by the registry instead of an `if` branch. No measurable change.

## Migration Plan

This is a refactor without external behavior change, so no DB migration. Steps:

1. Introduce `AuthorizationRegistry` class and the new module structure.
2. Move kanban's hardcoded entries out of auth and into kanban's composition wiring.
3. Update `SQLModelAuthorizationAdapter.check` to walk via the registry.
4. Migrate existing tests to use a registry fixture.
5. Run quality + tests. The wire format and HTTP behavior are unchanged, so e2e and integration tests pass without modification.

Rollback: revert the commit. No data to restore.

## Open Questions

- Should the registry expose introspection (e.g., `registered_resource_types()` for debug logging at startup)? *Likely yes; defer to implementation.*
- Should `seal()` be a separate concept or implicit on first read? *Explicit seal makes the lifecycle obvious; do that.*
