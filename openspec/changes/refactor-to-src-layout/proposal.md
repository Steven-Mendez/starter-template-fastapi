## Why

The repository currently treats `src/` as an importable package: every module imports siblings via the absolute prefix `from src.X import Y` and `src/__init__.py` exists for the sole purpose of making that prefix resolvable. This is the "rootdir-as-package" anti-pattern of Python layout. It conflates the *source directory* (a build/test concern) with the *package namespace* (a runtime concern), pollutes import paths with a meaningless `src.` prefix in every file, blocks tooling that assumes a real `src/` layout (mutmut, certain coverage configurations, distribution as a wheel), and makes the package non-relocatable: any consumer that vendors or installs the code inherits `src` as a top-level name. The follow-up `mutmut` re-introduction tracked in the archived `add-quality-automation` change is blocked on this.

## What Changes

- **BREAKING (internal)**: Adopt the standard Python "src layout": `src/` becomes the source root on `sys.path` rather than itself a package. `src/__init__.py` is deleted.
- Rewrite every import: `from src.features.users.X import Y` → `from features.users.X import Y`; `import src.platform.config.settings` → `import platform.config.settings`. Approximately 736 import statements across 205 files.
- **BREAKING (entrypoint)**: Console / Docker / Make / CI entrypoints flip from `src.main:app`, `src.worker`, `python -m src.worker` to `main:app`, `worker`, `python -m worker`. Affects `pyproject.toml` (`[tool.fastapi] entrypoint`), `Dockerfile` `CMD` lines, `Makefile` (`make worker`, `make outbox-retry-failed`, smoke import), and `alembic/env.py` model imports.
- Update `pyproject.toml` to put `src/` on the package path: `[tool.uv] package = false` is unaffected, but pytest's `testpaths` and ImportLinter's `source_modules` / `forbidden_modules` lose the `src.` prefix on every contract (~102 lines across nine contracts — every contract names modules with the prefix).
- Update `alembic.ini` `prepend_sys_path` so `alembic` invocations resolve modules without the `src.` prefix.
- Update `CLAUDE.md`, `README.md`, and `docs/*` references that name modules by their dotted path.
- The `platform/` directory name now shadows Python's stdlib `platform` module at the top of `sys.path`. **Rename `src/platform/` → `src/app_platform/`** as part of this change to avoid the collision; this is the largest mechanical edit of the refactor.
- Unblock the deferred follow-up: re-introduce `mutmut` in a separate change once this lands.

## Capabilities

### New Capabilities

- `project-layout`: How the repository's Python source is organised on disk and on `sys.path` — what the package roots are, how entrypoints reference modules, and how tooling (pytest, ImportLinter, Alembic, Docker, Make, FastAPI CLI) discovers them.

### Modified Capabilities

<!-- None. This refactor changes structural conventions, not the behaviour described by any existing capability spec. -->

## Impact

- **Source files**: ~368 Python files in `src/`; ~205 contain `src.`-prefixed imports that must be rewritten. Mechanical and scriptable (regex on import lines), but the diff will be large.
- **Entrypoints**: `Dockerfile` (2 `CMD` lines), `Makefile` (`make worker`, `make outbox-retry-failed`, `make smoke`-equivalent), `pyproject.toml` (`[tool.fastapi]`), `.github/workflows/*.yml` (any explicit module references), `alembic/env.py` (4 model imports + 1 settings import).
- **ImportLinter contracts**: every contract in `pyproject.toml` (`[tool.importlinter]`) names modules with the `src.` prefix. All ~102 lines must be rewritten. The contracts themselves remain semantically identical.
- **The `platform/` rename**: every import of `src.platform.X` becomes `app_platform.X`. The directory move + import rewrite must happen atomically in one commit so `make ci` passes.
- **Tests**: `pytest` discovers tests from `testpaths = ["src"]`; that stays correct, but if `src/conftest.py` participates in fixture discovery via being a package, removing `src/__init__.py` may shift conftest resolution. Mitigation: keep `src/conftest.py` (pytest finds rootdir-relative conftests regardless of package status).
- **Downstream consumers**: none — this is an application repo, not a published library. No public API change.
- **Coverage / mutation tooling**: unblocks `mutmut` (tracked separately) and clarifies coverage paths.
- **Reviewer load**: large mechanical diff. The proposal commits to landing it as **one PR** — splitting risks an inconsistent `sys.path` state where some files use `src.` and others don't, breaking imports. See `design.md` for the migration strategy.
