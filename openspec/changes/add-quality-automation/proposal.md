## Why

The CI gate today measures only line coverage (80% floor) but never actually fires that gate on every PR — the existing `make ci` runs `make test`, which does **not** invoke pytest-cov, so the 80% floor is a no-op end-to-end. Branch coverage was switched on in `pyproject.toml` (`branch = true`) but is also never measured, because no coverage target passes `--cov-branch`. Dependency hygiene is unmanaged on a stack that pins `fastapi`, `sqlmodel`, `pydantic`, and other co-versioned packages: the previous `.github/dependabot.yml` was removed in recent work and nothing replaced it. A single change closes those gaps with three coordinated additions.

## What Changes

- Wire **branch coverage** so it is actually measured (`--cov-branch` on every coverage target) and **gated** in CI via a `BRANCH_COVERAGE_FLOOR` enforced after each coverage run.
- Route `make ci` (and `make ci-local`) through `make cov` instead of `make test`, so the existing 80% line-coverage gate and the new branch-coverage gate both fire on every CI run. Update `.github/workflows/ci.yml` to match.
- Add **Renovate** (`renovate.json` at repo root) replacing the deleted Dependabot config. Group `pytest-*`, `fastapi`+`starlette`+`pydantic`, `sqlmodel`+`sqlalchemy`+`alembic`, `arq`+`redis`, `boto3` and dev-tooling so co-versioned bumps land together. Enable weekly lockfile maintenance.
- **SHA-pin** every `uses:` reference in `.github/workflows/*.yml` to a full commit SHA with a trailing `# <version>` comment, so Renovate's `github-actions` manager can maintain them deterministically.
- Document the new gates and the Renovate cadence in `docs/development.md`, `README.md`, and `CLAUDE.md`.

**Out of scope:** mutation testing. We investigated `mutmut` 2.x and 3.x and confirmed both fail on this repo's import layout (`src/__init__.py` makes `src` a package; mutmut hardcodes an assertion that rejects module names starting with `src.`). Making mutmut work requires refactoring the project to the standard Python "src layout" (no top-level `src/__init__.py`, imports without the `src.` prefix), which touches every Python file and merits its own dedicated change. Tracked as a follow-up.

## Capabilities

### New Capabilities
- `quality-automation`: Branch-coverage gating, Renovate-managed dependency and GitHub-Actions updates, and SHA-pinned action references for the template.

### Modified Capabilities
<!-- None — no existing feature spec's requirements change. The new gates wrap existing test surfaces without altering feature behavior. -->

## Impact

- **Code**: `pyproject.toml` (coverage comments), `Makefile` (`BRANCH_COVERAGE_FLOOR`, `--cov-branch` on coverage targets, new `check-branch-coverage` private target, `ci`/`ci-local` routed through `cov`), `.github/workflows/ci.yml` (SHA-pinned actions, `make cov` instead of `make test`), `renovate.json` (new).
- **CI runtime**: branch coverage adds negligible time; coverage-on-CI replaces the unused line floor (no change in total time).
- **Docs**: `docs/development.md` gains "Quality Gates" and "Dependency Updates" sections; `README.md` and `CLAUDE.md` Commands tables note the line+branch gate.
- **No runtime / API / migration impact** — purely tooling and dev-loop.
