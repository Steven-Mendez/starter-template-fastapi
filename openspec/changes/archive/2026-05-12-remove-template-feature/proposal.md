## Why

The `_template` feature (the `things` CRUD example) was shipped as an executable scaffold to copy from, not as production functionality. It is now baggage: every architecture contract lists it, the `things` table sits in every fresh database, and new operators have to read it to learn it is not theirs. Removing it cleans the starter back to the platform-and-supporting-features it actually offers, and forces the scaffolding instructions to live where they belong (docs + git history) instead of as a permanent live feature.

## What Changes

- **BREAKING**: Delete the entire `src/features/_template/` tree (domain, application, adapters, composition, tests, README).
- **BREAKING**: Remove the `things` table from the schema via a new forward-only Alembic migration that drops `things` and purges any `relationships` rows with `resource_type='thing'`.
- **BREAKING**: Strip `_template` wiring out of `src/main.py` — imports, `build_template_container`, `mount_template_routes`, `attach_template_container`, `register_template_authorization`, and the lifespan shutdown call.
- Drop `src.features._template` from every Import Linter `forbidden_modules` list in `pyproject.toml` (three contracts: email, background-jobs, file-storage isolation).
- Remove `_template` from the `make test-feature FEATURE=_template` example line in `CLAUDE.md` and from `docs/feature-template.md` (the doc that points at the directory as the starting point).
- Keep the *concept* of "copy a feature to start a new one" alive in docs by pointing operators at the now-archived `_template` directory in git history (e.g., `git show 'main~1:src/features/_template'`) or the `examples/kanban` branch.
- Tests: delete `src/features/_template/tests/**`; no other feature's tests reference `_template` directly (cross-feature isolation is enforced by contract), so nothing else moves.

This is intentional, surgical removal. No replacement scaffold ships in this change.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- The `_template` feature has no spec under openspec/specs/ today, so there is no
     existing capability whose requirements change. The deletion is purely an
     implementation-level removal: no spec deltas required. -->

## Impact

- **Code**: `src/features/_template/**` (entire tree), `src/main.py` (lifespan wiring), `pyproject.toml` (importlinter contracts).
- **Database**: new Alembic head that drops `things` and deletes `relationships` rows with `resource_type='thing'`. The old `20260511_0008_template_things_table.py` revision stays in history (forward-only); fresh DBs replay create-then-drop, existing DBs only run the drop.
- **HTTP API**: the entire `/things` namespace is removed — `POST /things`, `GET /things`, `GET /things/{id}`, `PATCH /things/{id}`, `POST /things/{id}/attachments`, `DELETE /things/{id}`. Any client still calling these endpoints will get 404 after deploy.
- **Authorization registry**: the `thing` resource type and its `owner ⊇ writer ⊇ reader` hierarchy stop being registered at startup.
- **Docs**: `CLAUDE.md`, `docs/feature-template.md`, and `README.md` references to `_template` need to be updated or removed.
- **Examples branch**: `examples/kanban` rebases onto `main` weekly; the next rebase will conflict if it still expects `_template` to exist. We accept that — the kanban branch is example-quality, not a contract.
- **Out of scope**: shipping a new "how to start a feature" scaffold. That can be a separate proposal if we miss it.
