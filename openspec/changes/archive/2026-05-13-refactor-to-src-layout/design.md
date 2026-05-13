## Context

The repo currently has `src/__init__.py` so the entire codebase is reachable as the `src` package. Every internal import is absolute against this root: `from src.features.users.application import ...`. Tooling references modules the same way: `pyproject.toml` declares `[tool.fastapi] entrypoint = "src.main:app"`, the `Dockerfile` runs `uvicorn src.main:app`, the Makefile runs `python -m src.worker`, `alembic/env.py` imports `src.platform.config.settings` and four `src.features.*.adapters.outbound.persistence.sqlmodel.models` modules, and every ImportLinter contract names modules with the `src.` prefix.

This is the classic "src layout" done wrong. In the canonical src layout, `src/` is a *source root* (a path put on `sys.path`) — not a package. Modules import each other by their real names (`features.users.X`), and the `src.` prefix never appears anywhere. The current setup gives no benefit over a flat layout while paying every cost of being unusual: it confuses contributors, blocks tools that hardcode the src-layout convention (notably `mutmut` for module discovery), and makes the project non-distributable as a wheel without first being renamed.

The follow-up `mutmut` re-introduction tracked in `add-quality-automation` task 6.3 is explicitly blocked on completing this work. The blast radius is large but mechanical: ~736 import statements across ~205 files, plus ~50 lines of ImportLinter contract paths, plus 5–6 entrypoint references.

A wrinkle: `src/platform/` shadows Python's stdlib `platform` module. With `src/__init__.py` present this is fine because the import is `src.platform`. Without it, putting `src/` first on `sys.path` makes `import platform` resolve to our directory, breaking `uvicorn`, `httpx`, and anything else that imports stdlib `platform` (for OS detection, user-agent strings, etc.). The shadowing must be resolved as part of the same atomic change.

## Goals / Non-Goals

**Goals:**

- Adopt the canonical src layout: `src/` on `sys.path`, no `src/__init__.py`, no `src.` prefix in any import.
- Resolve the `platform/` stdlib shadow by renaming the directory to `app_platform/`.
- Keep all existing behaviour identical: every endpoint, use case, worker job, migration, test, and ImportLinter contract behaves exactly as before. This is a *mechanical* refactor.
- Land in **one PR**: any partial state (some files use `src.`, others don't) breaks imports project-wide.
- Update CI, Docker, Make, Alembic, FastAPI-CLI, and ImportLinter so `make ci` is green at the tip of the change.
- Refresh `CLAUDE.md`, `README.md`, and `docs/*` so module references in prose are accurate.

**Non-Goals:**

- No behavioural changes. No removed features, no new features, no renamed routes, no schema migrations.
- No reorganization of features, no merging or splitting of modules.
- Not re-introducing `mutmut` — that is its own follow-up change once this lands.
- Not distributing as a wheel. We're adopting the layout because it is the standard, not because we plan to publish.
- Not converting `src/conftest.py` into a top-level conftest — pytest already discovers it correctly via `testpaths`.

## Decisions

### Decision 1: `src/` is a source root, not a package

**Choice**: Delete `src/__init__.py`. Put `src/` on `sys.path` via `pyproject.toml`'s `[tool.pytest.ini_options] pythonpath = ["src"]`, `alembic.ini`'s `prepend_sys_path = src`, and `PYTHONPATH=src` in the `Dockerfile` and `Makefile` targets that invoke modules directly.

**Why**:
- This is the convention every modern Python project follows (FastAPI itself, `httpx`, `pydantic`, `sqlmodel`, …). Familiarity is the point.
- pytest's `pythonpath` setting was designed precisely for this and avoids the need for editable installs.
- uvicorn / FastAPI CLI honour `PYTHONPATH` natively, so the Docker `CMD` becomes `PYTHONPATH=src uvicorn main:app …` (or equivalently, set `ENV PYTHONPATH=src` once and keep the CMD clean).

**Alternative considered**: keep `src/__init__.py` and prefix everything with `src.` — i.e. status quo. Rejected because it's the cost we're paying without a benefit, and it blocks `mutmut`.

**Alternative considered**: editable install (`uv pip install -e .` with `[tool.hatch.build.targets.wheel] packages = ["src/features", "src/app_platform"]` etc.). Rejected — adds a build step, complicates Docker layer caching, and we don't need wheel distribution.

### Decision 2: Rename `src/platform/` → `src/app_platform/`

**Choice**: The directory currently named `platform` is renamed to `app_platform`. Every `from src.platform.X` becomes `from app_platform.X`. The project's `CLAUDE.md` and `docs/*` use the new name throughout.

**Why**:
- Once `src/` is first on `sys.path`, `import platform` (stdlib) gets shadowed by our directory. Even if we never use stdlib `platform` directly, transitive deps do (uvicorn reads `platform.system()`, httpx builds its User-Agent from `platform.python_version()`, etc.). A shadow at the root of `sys.path` is a latent footgun.
- The alternative (insert `src/` *after* the stdlib in `sys.path`) is fragile: editable installs, `python -c`, and IDE module resolution don't all respect the same ordering.
- `app_platform` keeps the name short and self-describing. We considered `platform_` (trailing underscore) and `kernel`; `app_platform` won for readability.

**Alternative considered**: rename to `core/`. Rejected — `core` is overloaded; readers expect domain-specific code there, and our directory holds composition, config, persistence base classes, and middleware (i.e. exactly platform concerns).

**Alternative considered**: namespace-package the directory under `app/`. Rejected — adds a layer of indirection for no gain.

### Decision 3: One atomic PR, no transitional state

**Choice**: The full migration — delete `__init__.py`, rename `platform/` → `app_platform/`, rewrite every import, update every config — ships as one commit (or one tight series squashed at merge).

**Why**:
- A half-migrated tree doesn't import. There is no meaningful checkpoint between "all `src.` prefixes" and "no `src.` prefixes".
- The diff is mostly mechanical (regex + `git mv`). The reviewer's actual cognitive load is in the ~10 hand-edited config files, which fit on one screen.
- ImportLinter runs in CI on the same PR and catches anything the regex missed.

**Alternative considered**: ship the rename + entrypoint change first, then a follow-up to clean import prefixes. Rejected — there's no working intermediate state. Either `src.platform` is the import (and the rename hasn't happened) or `app_platform` is (and the rename must be complete in the same commit).

### Decision 4: Migration is script-assisted, not manual

**Choice**: Use a `sed`/`ruff`-driven script (committed under `scripts/refactor_to_src_layout.py` *temporarily* — deleted at the end of the change) that performs:

1. `git mv src/platform src/app_platform` (single rename, preserves git history).
2. Project-wide regex on `*.py` files only: `^(\s*)(from|import)\s+src\.platform\b` → `\1\2 app_platform`; then `^(\s*)(from|import)\s+src\.(features|conftest|main|worker)\b` → `\1\2 \3`.
3. Delete `src/__init__.py`.
4. Sweep config files explicitly (small allowlist: `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `Dockerfile`, `Makefile`, `.github/workflows/*.yml`).
5. Run `make format && make lint-fix && make typecheck && make lint-arch && make cov && make test-integration` and iterate until clean.

The script is deleted in the final commit of the change — it's a one-shot.

**Why**:
- Hand-editing 205 files invites typos. A targeted regex is auditable in one screen of code.
- Keeping the script around as an artifact tempts future "I'll just re-run it" misuses. Delete it.
- ImportLinter is the safety net: it'll flag any forgotten `src.X` reference.

**Alternative considered**: `libcst` or `rope` codemod. Rejected — overkill for a prefix-strip; line-anchored regex catches every real case in this codebase (verified: no `src.` appears mid-line in any import, no string-form imports, no `importlib.import_module("src.X")` calls).

### Decision 5: Defer `mutmut` re-introduction

**Choice**: Do not add `mutmut` configuration in this change. Track it as a separate follow-up.

**Why**:
- Mixing the layout refactor with a new tool muddies the PR's purpose and complicates rollback.
- The archived `add-quality-automation` change already names this as a follow-up.

## Risks / Trade-offs

- **[Risk] Missed `src.` reference breaks runtime, not CI** → Mitigation: ImportLinter contracts run in CI and reference every module by absolute path. If a contract path is wrong, ImportLinter fails. If an import statement is wrong, the integration tests fail (they exercise the full composition root). The combination catches both classes of miss.
- **[Risk] `platform/` rename misses a string-form import or a `__import__` call** → Mitigation: pre-sweep grep for the literal strings `"src.platform"`, `'src.platform'`, `"platform.` (as a left-anchor at column 0 in imports) before running the regex. The codebase has no `importlib.import_module` calls against internal modules (verified).
- **[Risk] `alembic/env.py` autogenerate breaks if model imports are wrong** → Mitigation: include `uv run alembic check` (or `alembic revision --autogenerate --sql` against an empty diff) in the tasks list. If autogenerate fails to detect tables, model imports are wrong.
- **[Risk] Docker layer cache invalidated; image rebuilds slowly on first push** → Acceptable. This is a one-time cost.
- **[Risk] IDE indexes go stale after the rename, dev experience temporarily bad** → Mitigation: nothing to do in CI, but call it out in the PR description so reviewers know to re-index.
- **[Risk] `src/__init__.py` deletion changes pytest's rootdir/conftest discovery** → Mitigation: pytest's `rootdir` is determined by `pyproject.toml` location, not package layout. `src/conftest.py` is still picked up via `testpaths`. Verify by running `make test` after the change.
- **[Trade-off] Large mechanical diff** → We accept this. The alternative is years of stale `src.` prefix.

## Migration Plan

1. **Pre-flight on `main`**: confirm `make ci` is green so any subsequent failure is attributable to the refactor, not a pre-existing issue.
2. **Branch**: `refactor/src-layout`.
3. **Single PR sequence** (all in one branch, can be one squash-merged commit):
   1. `git mv src/platform src/app_platform`.
   2. Run the rewrite script. Inspect the resulting diff; spot-check a handful of files.
   3. Delete `src/__init__.py`.
   4. Hand-edit `pyproject.toml` (`[tool.fastapi] entrypoint`, `[tool.pytest.ini_options] pythonpath`, `[tool.importlinter]` contracts), `alembic.ini` (`prepend_sys_path`), `alembic/env.py` (5 imports), `Dockerfile` (2 `CMD` lines + add `ENV PYTHONPATH=src`), `Makefile` (`make worker`, `make outbox-retry-failed`, smoke), and any `.github/workflows/*.yml` that name `src.X`.
   5. Update `CLAUDE.md`, `README.md`, `docs/*` prose to drop the `src.` prefix and rename `platform` → `app_platform` where module names appear.
   6. Run the local quality gate: `make quality && make cov && make test-integration`. Fix any miss.
   7. Delete the rewrite script. Commit.
4. **CI gate**: the PR must pass `make ci` and the existing docker-smoke / docker-compose / gitleaks workflows.
5. **Rollback**: revert the PR. Because the refactor is mechanical and self-contained, revert is safe at any point post-merge.

## Open Questions

- None blocking. The `app_platform` name is a judgement call; if the user prefers a different name (`infra`, `runtime`, `host`), it's a one-line change to the rewrite script.
