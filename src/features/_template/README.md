# `_template` — the starter feature

This is the executable starting point for a new feature. It models a
single resource called `Thing` with full CRUD over HTTP, ReBAC-gated
authorization, SQLModel persistence, and a complete test suite.

When starting a new feature in your project:

1. Copy the directory: `cp -r src/features/_template src/features/<your-feature>`
2. Rename the package: `find src/features/<your-feature> -type f -name '*.py' -exec sed -i '' 's/_template/<your-feature>/g; s/Thing/<YourEntity>/g; s/thing/<your-entity>/g' {} +`
3. Rename the table and migration: edit `adapters/outbound/persistence/sqlmodel/models.py` and add a new Alembic migration
4. Mount the routes in `src/main.py` and wire the container into the lifespan
5. Register your resource type with the authorization registry
6. Update or rewrite the tests

The `_template` itself stays committed and wired into `src/main.py` so a
fresh clone always has a known-good reference feature serving `/things`.
