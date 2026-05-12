## Context

The `_template` feature (resource type `thing`, HTTP namespace `/things`) was added at revision `20260511_0008` as a worked single-resource CRUD example. Today it is wired into the composition root, owns a table in the schema, is referenced by three Import Linter contracts, and registers a resource type with the authorization registry on every boot. None of that is product surface — it is documentation that happens to run.

Relevant footprint discovered during proposal work:

- `src/features/_template/` — domain (`Thing`), application (use cases, ports), adapters (HTTP router at `/things`, SQLModel `ThingTable`), composition (`build_template_container`, `mount_template_routes`, `register_template_authorization`, `attach_template_container`), tests, README.
- `src/main.py` — lines 18–22 imports, line 123 (`mount_template_routes`), lines 190–201 (container build + authz registration), line 218 (`attach_template_container`), line 239 (`template.shutdown()`).
- `pyproject.toml` — `src.features._template` appears in the `forbidden_modules` of three contracts (email/jobs/file-storage isolation).
- `alembic/versions/20260511_0008_template_things_table.py` — creates `things`. Chained between `..._0007` (relationships) and `..._0009_credentials_table`.
- `docs/feature-template.md`, `CLAUDE.md`, `README.md` — operator-facing references to the directory.
- The platform-owned `relationships` table holds rows with `resource_type='thing'` once any thing is created.

This change deletes all of that.

## Goals / Non-Goals

**Goals:**

- Remove the `_template` feature from the running application: no routes, no container, no startup wiring, no authorization registry entry.
- Drop the `things` table and any `thing`-typed rows in `relationships` cleanly, with a forward-only Alembic migration that works on both fresh and already-deployed databases.
- Keep the rest of the architecture contracts intact and passing (`make lint-arch`, `make quality`, `make ci`).
- Leave the codebase in a state where "how to start a new feature" is answered by docs + git history, not by a live feature.

**Non-Goals:**

- Shipping a replacement scaffold. If the team misses the worked example, that is a separate proposal.
- Touching the `examples/kanban` branch in this repo. That branch rebases weekly; the next rebase will resolve the conflict.
- Down-migration support. Migrations in this repo are forward-only.
- Repointing existing clients of `/things`. There are none in production; any stragglers will see 404.

## Decisions

### Decision: forward-only "drop things" migration on top of head

Add a new Alembic revision (`20260514_0011_drop_template_things.py` — name TBD at apply time) whose `upgrade()` does, in order:

1. `DELETE FROM relationships WHERE resource_type = 'thing';`
2. `op.drop_table("things")`.

`downgrade()` is `pass` (forward-only convention in this repo, consistent with the surrounding revisions).

**Alternative considered**: squash by deleting `20260511_0008_template_things_table.py` and rewriting `down_revision` on `..._0009`. Rejected — rewriting migration history breaks every existing database. Forward-only is the established convention here (see `20260513_0010_drop_users_password_hash.py`).

### Decision: delete the directory wholesale, no soft-deprecation period

Remove `src/features/_template/` in one commit rather than emptying its router first. Three reasons:

- The Import Linter contracts already isolate it. No production feature imports from it.
- `mount_template_routes` and the container build happen unconditionally in `main.py`'s lifespan — there is no feature flag to flip off, and adding one for a single-cut deletion is gold-plating.
- Half-deleted features rot faster than absent ones.

### Decision: scrub `_template` from Import Linter contracts in the same change

Three `forbidden_modules` lists in `pyproject.toml` (email, background-jobs, file-storage isolation) name `src.features._template`. After deletion the entry becomes a dead reference. Import Linter does not fail on missing modules in `forbidden_modules`, but leaving them is noise that drifts. Strip them.

### Decision: docs update is part of the same change, not a follow-up

`docs/feature-template.md` literally documents the directory we are deleting; `CLAUDE.md` cites `make test-feature FEATURE=_template` as an example; `README.md` references the scaffold. Shipping the code change without the doc change leaves contradictory instructions in the repo for as long as the doc-only PR takes. They land together.

The "how to start a new feature" guidance moves to a short note pointing at `git log -- src/features/_template` (or a tagged commit before deletion) and the `examples/kanban` branch.

### Decision: no spec deltas

The proposal's Capabilities section is empty. `openspec/specs/` today contains `authentication/` and `authorization/` only — `_template` was never specced. There is no existing requirement whose behavior changes; this is an implementation-level deletion. The specs phase produces no files for this change.

## Risks / Trade-offs

- **Risk**: a deployment runs the migration but an old app container still in rolling-update talks to the dropped table. → Mitigation: `things` is touched only by `_template` routes. Once the migration succeeds, the only callers gone are old `/things/*` handlers, which will fail-and-retry harmlessly. No other feature reads `things`.
- **Risk**: `relationships` rows with `resource_type='thing'` exist in a deployed DB and the `DELETE` step is slow on a large table. → Mitigation: this is a single-resource example feature; row counts are expected to be tiny. If a deployment somehow has millions of `thing` tuples, the migration is a `DELETE WHERE resource_type = 'thing'` on an indexed column and will run in seconds. We are accepting the risk rather than batching.
- **Risk**: the `examples/kanban` branch's weekly rebase breaks. → Mitigation: explicitly out of scope (see Non-Goals). The branch is example-quality; the rebase author will fix it forward.
- **Trade-off**: new operators lose the in-tree worked example. → We accept this. The directory survives in git history; `docs/feature-template.md` can be rewritten as a short pointer rather than a directory walkthrough.
- **Trade-off**: this is a BREAKING change for any client of `/things/*`. → Acceptable. `_template` was always documented as scaffolding, not API.

## Migration Plan

1. Land the code + migration + docs together in one PR.
2. On deploy: Alembic runs the new revision, `things` is dropped, orphan `relationships` rows are purged.
3. Old `/things/*` requests return 404 from FastAPI's default not-found handler (the routes are simply no longer mounted).
4. Rollback strategy: revert the PR and run nothing. The dropped table cannot be brought back without restoring from backup; we are accepting that because `_template` carried no production data.

## Open Questions

- None blocking. Naming of the new migration revision ID is left to apply time so it picks up the correct timestamp.
