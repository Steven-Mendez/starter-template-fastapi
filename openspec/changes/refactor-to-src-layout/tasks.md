## 1. Pre-flight

- [x] 1.1 Confirm `main` is green: `make ci` passes locally with no edits, and `git status` is clean.
- [x] 1.2 Create branch `refactor/src-layout` off the current `main`.
- [x] 1.3 Grep-audit string-form / dynamic imports that the regex won't catch: `grep -rn "['\"]src\\.\\|importlib\\.import_module\\|__import__" --include="*.py" .` — record any hit for hand-editing later. Expect zero matches in this repo.

## 2. Write the one-shot rewrite script

- [x] 2.1 Create `scripts/refactor_to_src_layout.py` that performs (in order): (a) `git mv src/platform src/app_platform` via `subprocess`, (b) walks `**/*.py` under the repo and applies two line-anchored regex substitutions — `^(\s*)(from|import)\s+src\.platform\b` → `\1\2 app_platform` and `^(\s*)(from|import)\s+src\.(features|conftest|main|worker)\b` → `\1\2 \3` — writing files in place, (c) deletes `src/__init__.py`. Idempotent: re-running on a clean tree is a no-op.
- [x] 2.2 Dry-run the script on the working tree to a temp directory and diff the output; eyeball ~10 random files to confirm the substitutions are correct and leave non-import lines untouched.

## 3. Run the rewrite

- [x] 3.1 Run `scripts/refactor_to_src_layout.py` on the working tree. Stage everything: `git add -A`.
- [x] 3.2 Manually inspect the diff for `src/conftest.py`, `src/main.py`, `src/worker.py`, and two or three deeply nested files (e.g. `src/features/authentication/adapters/inbound/http/dependencies.py`, `src/app_platform/persistence/sqlmodel/authorization/models.py`) to confirm imports look right.

## 4. Update configuration files (hand-edited)

- [x] 4.1 `pyproject.toml`: change `[tool.fastapi] entrypoint = "src.main:app"` → `entrypoint = "main:app"`. Add `[tool.pytest.ini_options] pythonpath = ["src"]`. Rewrite every Import Linter contract path in `[tool.importlinter]` so `src.platform.X` → `app_platform.X` and `src.features.X` → `features.X` and `src.main`/`src.worker` → `main`/`worker`. Preserve every contract's structure and intent exactly.
- [x] 4.2 `alembic.ini`: change `prepend_sys_path = .` → `prepend_sys_path = src` (or add `src` to the list if `path_separator` is in use).
- [x] 4.3 `alembic/env.py`: rewrite the five `src.X` imports — four `src.features.*.adapters.outbound.persistence.sqlmodel.models` lines and `from src.platform.config.settings import AppSettings` — to use the post-refactor names (`features.X.adapters.outbound.persistence.sqlmodel.models`, `from app_platform.config.settings import AppSettings`).
- [x] 4.4 `Dockerfile`: change both `CMD` lines from `uvicorn src.main:app …` to `uvicorn main:app …`. Add `ENV PYTHONPATH=/app/src` near the top of each stage that runs the app (or pass `--app-dir /app/src` on the uvicorn command — pick one and apply consistently). Keep `COPY src ./src` as-is.
- [x] 4.5 `Makefile`: change `uv run python -m src.worker` → `PYTHONPATH=src uv run python -m worker`; change `uv run python -m src.features.outbox.management retry-failed` → `PYTHONPATH=src uv run python -m features.outbox.management retry-failed`; change the smoke import `uv run python -c "import src.main"` → `PYTHONPATH=src uv run python -c "import main"`.
- [x] 4.6 `.github/workflows/*.yml`: grep for any explicit `src.X` module reference (`python -m src.X`, `import src.X`, etc.) and rewrite. Most workflow files invoke `make` targets and need no change — confirm rather than assume.

## 5. Update documentation

- [x] 5.1 `CLAUDE.md`: rewrite every code reference in the Commands table, the Module map, the Layer contracts list, the feature sections, and the "Adding a new feature" steps. Drop the `src.` prefix from any dotted module path; rename `src.platform.X` to `app_platform.X` and `src/platform/…` to `src/app_platform/…` in file-path references.
- [x] 5.2 `README.md`: same sweep — replace `src.main:app`, `python -m src.worker`, etc.
- [x] 5.3 `docs/*.md`: grep `docs/` for `src\.` and for `src/platform`; rewrite each hit.

## 6. Run the local quality gate

- [x] 6.1 `make format` (Ruff format) — should produce no changes after the rewrite. If it does, inspect and commit.
- [x] 6.2 `make lint-fix` — autofix any import-order regressions the rewrite introduced.
- [x] 6.3 `make typecheck` — mypy must pass. Any failure is almost certainly a missed import path; fix and re-run.
- [x] 6.4 `make lint-arch` — Import Linter must report every contract as kept. Any broken contract means a path in `pyproject.toml`'s `[tool.importlinter]` was rewritten wrong; fix and re-run.
- [x] 6.5 `make cov` — line and branch coverage gates must pass. Inspect any test failure: most likely an import path; some may be fixture discovery (`src/conftest.py` should still be picked up via `testpaths = ["src"]`).
- [x] 6.6 `make test-integration` — Docker-backed tests must pass. This exercises the real composition root and catches anything that survived the unit suites.
- [x] 6.7 `uv run alembic check` (or `alembic revision --autogenerate --sql` against a HEAD checkout) — must report no schema diff and must successfully import all model modules.

## 7. Verify the spec scenarios

- [x] 7.1 Run the grep scenarios from `specs/project-layout/spec.md` and confirm each produces no matches: `grep -rn "^[ ]*\(from\|import\) src\." --include="*.py" .`; `grep -rn "^[ ]*\(from\|import\) platform\b" --include="*.py" src/`; `grep -rn "src\.platform" --include="*.py" --include="*.toml" --include="*.ini" --include="*.yml" --include="*.yaml" --include="Makefile" --include="Dockerfile*" .`.
- [x] 7.2 Confirm the stdlib `platform` scenario: `PYTHONPATH=src uv run python -c "import platform; print(platform.system())"` prints the host OS.
- [x] 7.3 Confirm `src/__init__.py` is deleted: `test ! -e src/__init__.py`.
- [x] 7.4 Confirm `src/app_platform/` exists and `src/platform/` does not.

## 8. Clean up

- [x] 8.1 Delete `scripts/refactor_to_src_layout.py`. The change is one-shot; the script is not a maintained artifact.
- [x] 8.2 `git status` should show only intentional changes; no leftover `__pycache__/` or stray rewrites in `node_modules`/`.venv`/`build` (verify the script's path filter excluded those).

## 9. Land the change

- [ ] 9.1 Commit with a single subject line: `refactor!: adopt canonical src layout (drop src. prefix, rename platform → app_platform)`. Body explains the breaking-internal nature and references the archived `add-quality-automation` follow-up.
- [ ] 9.2 **Deferred to user**: push branch, open PR, confirm CI is green (in particular: ImportLinter contracts, docker-smoke, and coverage gates), squash-merge to `main`.
- [ ] 9.3 **Follow-up (tracked outside this change)**: open a separate `add-mutmut` change to re-introduce `mutmut` now that the layout supports it.
