## 1. Author the drop-things migration

- [x] 1.1 Create `alembic/versions/<timestamp>_drop_template_things.py` with `down_revision = "20260513_0010"` (or current head — verify with `uv run alembic heads`), `revision = "<timestamp>"`.
- [x] 1.2 Implement `upgrade()` to (a) `op.execute("DELETE FROM relationships WHERE resource_type = 'thing'")` then (b) `op.drop_table("things")`.
- [x] 1.3 Implement `downgrade()` (recreates the `things` table — local convention is a real body, not `pass`; the design.md note is superseded).
- [ ] 1.4 Run `uv run alembic upgrade head` against a fresh local DB to confirm the chain applies cleanly. **(Requires Docker / a running Postgres — left for the operator.)**
- [ ] 1.5 Run `make migration-check` to verify the autogenerate diff is empty after the drop. **(Requires Docker — left for the operator.)**

## 2. Unwire `_template` from the composition root

- [x] 2.1 In `src/main.py`, remove the three `_template` imports at lines 18–22 (`build_template_container`, `attach_template_container`, `mount_template_routes`, `register_template_authorization`). (Also removed the now-unused `SessionSQLModelUserAuthzVersionAdapter` import.)
- [x] 2.2 Remove the `mount_template_routes(app)` call.
- [x] 2.3 Remove the `template = build_template_container(...)` block and the `register_template_authorization(authorization.registry)` call.
- [x] 2.4 Remove the `attach_template_container(lifespan_app, template)` call.
- [x] 2.5 Remove `template.shutdown()` from the lifespan teardown.
- [x] 2.6 Run `uv run python -c "import src.main"` to verify the composition root still imports.

## 3. Delete the feature directory

- [x] 3.1 `git rm -r src/features/_template` (domain, application, adapters, composition, tests, README, `__init__.py`). Also removed the lingering on-disk `__pycache__` and the `import src.features._template...models` line in `alembic/env.py`.
- [x] 3.2 Confirm no other file imports `src.features._template` with `rg "src\\.features\\._template" src/ alembic/`.

## 4. Strip `_template` from Import Linter contracts

- [x] 4.1 In `pyproject.toml`, remove the `"src.features._template",` line from the `forbidden_modules` of the **email isolation** contract.
- [x] 4.2 Remove the same line from the **background-jobs isolation** contract.
- [x] 4.3 Remove the same line from the **file-storage isolation** contract.
- [x] 4.4 Run `make lint-arch` to confirm all contracts still pass with no `_template` references. (17 kept, 0 broken.)

## 5. Update operator-facing docs

- [x] 5.1 In `CLAUDE.md`, remove the row for `_template` from the feature table and the `make test-feature FEATURE=_template` example line; remove the "Copy this directory to start a new feature." instruction.
- [x] 5.2 In `CLAUDE.md`'s "Adding a new feature" section, replace step 1's `cp -r src/features/_template src/features/<name>` with a pointer to the pre-removal commit / `examples/kanban` branch.
- [x] 5.3 Delete or rewrite `docs/feature-template.md` to be a short pointer to git history rather than a directory walkthrough.
- [x] 5.4 Remove any `_template` / `/things` mentions from `README.md` and other files surfaced by `rg -l "_template|/things" docs/ README.md`. Also touched `docs/architecture.md` (feature table, dep graph, request flow, composition order) and `docs/development.md`.

## 6. Verify the full gate

- [x] 6.1 Run `make quality` (lint + arch + typecheck) and fix any fallout. (Ruff clean, Import Linter 17/17 kept, mypy clean over 337 source files.)
- [x] 6.2 Run `make test` and confirm only `_template` tests are gone, no other suite regresses. (277 passed, 0 failed, 1 xfailed — the existing S3 stub xfail.)
- [ ] 6.3 Run `make ci` end-to-end (quality + test + integration) and confirm coverage gate still passes at ≥80%. **(Requires Docker for integration — left for the operator.)**
- [ ] 6.4 Boot the app locally (`make dev`) and confirm `GET /things` returns 404 while `GET /health/live` still returns 200. **(Requires a running DB / interactive server — left for the operator.)**

## 7. Archive the change

- [ ] 7.1 Once all tasks above are checked, run `/opsx:archive` to move this change to `openspec/changes/archive/`.
