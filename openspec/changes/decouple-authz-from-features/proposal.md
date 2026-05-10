## Why

The authorization layer inside `features/auth/application/authorization/` knows kanban by name. `actions.py` declares `ACTIONS["kanban"]`, `ACTIONS["column"]`, `ACTIONS["card"]`; `hierarchy.py` hardcodes `KANBAN_RELATION_HIERARCHY`; `resource_graph.py` exposes `board_id_for_card` and `board_id_for_column` on its `ParentResolver` Protocol. Auth is supposed to be a generic identity feature, but the engine inside it speaks the vocabulary of another bounded context.

This is a teaching bug for a starter template. A new feature added to a fork of this project would have to edit auth to register its actions, hierarchy, and parent walks — exactly the cross-feature coupling that hexagonal architecture is supposed to eliminate. The fix is small: replace the hardcoded resource maps with a registration API and have each feature declare its own authz config in its composition root.

## What Changes

- **BREAKING (internal API)** Make `actions.py` and `hierarchy.py` registries instead of constant tables. The auth feature ships only the `system` resource type pre-registered (because `system:main#admin` is auth's own concern via bootstrap); kanban registers `kanban`, `column`, and `card` from its own composition root.
- **BREAKING (internal API)** Generalize `ParentResolver` to a single `parent_of(resource_type, resource_id) -> tuple[str, str] | None` method that returns `(parent_type, parent_id)`. Drop `board_id_for_card` and `board_id_for_column`.
- Introduce an `AuthorizationRegistry` that owns the live action map, hierarchy map, and parent-walk map at runtime. The registry is the seam features write into and the engine reads from.
- Update `SQLModelAuthorizationAdapter.check` so the parent walk delegates to the registry and walks until it lands on a resource type that has stored relations (today: `kanban` and `system`). Multi-level walks (e.g., `card → column → board`) compose naturally instead of being hardcoded as a special case.
- Move kanban's authz declarations out of auth: kanban's `composition/wiring.py` calls `registry.register(...)` for its three resource types and the `kanban` hierarchy at startup.
- Auth's container exposes the registry on the container so `main.py` can hand it to kanban; no auth code references kanban after this change.
- No domain or HTTP behavior changes. Same routes, same checks, same wire format. The only externally visible difference is that the SpiceDB stub README now describes a generic registration model instead of a hardcoded one.
- Update tests that import `KANBAN_RELATION_HIERARCHY` etc.; replace with registry-driven equivalents. Add unit tests for registration semantics (registering twice is an error; missing resource type raises `UnknownActionError` at check time).

## Capabilities

### New Capabilities

<!-- No new capabilities. Behavior is identical; this is a pure refactor of the authorization capability's internal API. -->

### Modified Capabilities

- `authorization`: changes the *implementation contract* between the engine and the rest of the system — actions, hierarchy, and parent walks become runtime-registered rather than statically declared. No requirement on external behavior changes; the spec gains internal-API requirements covering the registry contract.

## Impact

- **`src/features/auth/application/authorization/`**:
  - `actions.py` becomes a thin module that exposes `Registry` operations and seeds only the `system` resource type.
  - `hierarchy.py` becomes registry-driven; the `_HIERARCHIES` constant is replaced by registry lookups.
  - `resource_graph.py` collapses to a single `parent_of` Protocol method and a registry-driven walker.
  - New `registry.py` (or co-locate in `actions.py`) holds the runtime maps and registration API.
- **`src/features/auth/adapters/outbound/authorization/sqlmodel/repository.py`**: `check` walks parents via the registry; same semantics, no hardcoded `if resource_type in {"card", "column"}` branches.
- **`src/features/auth/composition/container.py`**: the auth container exposes a `registry` field. Auth seeds `system` at construction; everything else is registered by other features.
- **`src/features/kanban/composition/wiring.py`** (or `container.py`): kanban registers its three resource types, the `owner ⊇ writer ⊇ reader` hierarchy, and the `parent_of` callable that walks `card → column → board`.
- **`src/main.py`**: passes the auth registry into `build_kanban_container` so kanban can register its config; no other change.
- **Tests**: existing engine/hierarchy tests rebind to the registry. Add three small registry tests (register-then-lookup, double-register error, unknown-type at check time).
- **SpiceDB stub README**: updated to describe how features would call into an authz schema-builder instead of editing a hardcoded map.
- **Out of scope**: splitting authorization out of the auth feature. That is the follow-up `split-authentication-and-authorization` proposal — this change deliberately stops at the boundary of "auth no longer hardcodes other features' vocabulary" so the two changes can land independently.
