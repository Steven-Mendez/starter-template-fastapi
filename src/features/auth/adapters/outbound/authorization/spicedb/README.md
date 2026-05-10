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
2. Translate `src/features/auth/application/authorization/actions.py`
   into the `.zed` schema below (or load the schema from a checked-in
   file at startup).
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

The schema below mirrors the rules in `application/authorization/actions.py`
and `application/authorization/hierarchy.py`. The `system` definition has
a single `admin` relation; the `kanban` definition shows the
`reader ⊆ writer ⊆ owner` hierarchy expressed as SpiceDB permissions.
Card and column resources are not declared as their own definitions in
this schema fragment because the in-repo engine resolves them via parent
walk; for a SpiceDB deployment you would add `column` and `card`
definitions with `permission read = board->read` (and similar for update
and delete) so the engine performs the inheritance natively.

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
