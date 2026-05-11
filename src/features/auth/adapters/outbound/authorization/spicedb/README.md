# SpiceDB authorization adapter (stub)

This adapter is a **structural placeholder**. Each method raises
`NotImplementedError`. It ships with the template to demonstrate that the
`AuthorizationPort` is the actual swap boundary between the application
layer and any ReBAC engine — the in-repo SQLModel adapter and a real
SpiceDB integration share the exact same surface.

## Why a stub?

A runnable SpiceDB integration would add a service to `docker-compose.yml`,
a gRPC client dependency, and a schema-watch pipeline. That is more
moving parts than a starter template should ship by default. The stub
keeps the seam visible without dragging in the infrastructure.

To wire up a real adapter:

1. Copy this package to a new project or replace the contents of
   `adapter.py` with a SpiceDB-backed implementation.
2. Translate the live `AuthorizationRegistry` content into the `.zed`
   schema below — or, equivalently, add a startup helper that walks the
   sealed registry (`registry.registered_resource_types()` + the
   per-type action/hierarchy maps) and uploads a `.zed` document to
   SpiceDB before the server starts serving traffic. Because every
   feature registers its types from its own composition root, no
   schema authoring is centralized in auth.
3. Update `AuthContainer` to construct `SpiceDBAuthorizationAdapter`
   instead of `SQLModelAuthorizationAdapter` (see
   `src/features/auth/composition/container.py`). The application layer
   does not change.

## Port → SpiceDB API mapping

| `AuthorizationPort` method | SpiceDB API           |
| -------------------------- | --------------------- |
| `check`                    | `CheckPermission`     |
| `lookup_resources`         | `LookupResources`     |
| `lookup_subjects`          | `LookupSubjects`      |
| `write_relationships`      | `WriteRelationships`  |
| `delete_relationships`     | `DeleteRelationships` |
| (cache invalidation)       | `WatchAPI` (optional) |

## Example `.zed` schema

The schema below mirrors the rules each feature contributes to the
`AuthorizationRegistry` at composition time. The `system` definition has
a single `admin` relation (registered by auth); the `kanban` definition
shows the `reader ⊆ writer ⊆ owner` hierarchy registered by the kanban
feature. For a SpiceDB deployment you would translate the registry's
inherited types into native definitions (`permission read = board->read`
and similar) so the engine resolves multi-level walks natively rather
than through this template's check-time parent walker.

```zed
definition user {}

definition system {
    relation admin: user

    permission manage_users = admin
    permission read_audit   = admin
}

definition kanban {
    relation reader: user
    relation writer: user
    relation owner:  user

    permission read   = reader + writer + owner
    permission update =          writer + owner
    permission delete =                   owner
}

definition column {
    relation board: kanban

    permission read   = board->read
    permission update = board->update
    permission delete = board->delete
}

definition card {
    relation column: column

    permission read   = column->read
    permission update = column->update
    permission delete = column->delete
}
```

## Cache invalidation

The in-repo adapter bumps `User.authz_version` on every relationship
write that affects a user, so the principal cache invalidates on the
next request. A SpiceDB-backed adapter would either:

* call `WatchAPI` to receive relationship updates and bump
  `authz_version` from a background subscriber, or
* drop server-side caching entirely and rely on SpiceDB's own caching
  (the `consistency` field controls staleness per request).

Either choice is local to the adapter; the application layer is unchanged.
