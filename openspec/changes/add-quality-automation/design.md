## Context

The template's `make ci` gate today runs Ruff, Import Linter, mypy, and `pytest` — but **not** with coverage. `make test`, the target that `ci` chains to, calls plain `uv run pytest -m "not integration"` with no `--cov` flag. The 80% line-coverage floor declared in `pyproject.toml [tool.coverage.report] fail_under` is only enforced when a developer runs `make cov` explicitly. CI never invokes that target.

Branch coverage is enabled in config (`[tool.coverage.run] branch = true`) but never measured: pytest-cov only emits branch data when invoked with `--cov-branch`, and no Make target passes it. Confirmed by inspecting `reports/coverage.json` — the `totals` block has `percent_statements_covered` but no `percent_branches_covered`.

Dependency hygiene is also unmanaged: `.github/dependabot.yml` was removed in the recent S3/Resend work and not replaced. The project ships pinned `fastapi`/`starlette`/`pydantic`/`sqlmodel`/`alembic`/`boto3`/`arq` versions and a `uv.lock`, so drift is silent until the next manual bump.

Stakeholders: anyone forking the template — the gates need to be useful but not so noisy they get disabled on day two.

## Goals / Non-Goals

**Goals:**
- Branch coverage measured on every coverage target and gated in `make ci` with a calibrated floor (start at current branch % rounded down to the nearest 5%; ratchet in a separate change).
- Route `make ci` and the GitHub `tests` job through a coverage-producing target so both the line and branch floors actually fire on every CI run.
- Renovate config that replaces the deleted Dependabot setup, groups co-versioned packages, manages `.github/workflows/*.yml` action SHAs, and runs lockfile maintenance weekly.
- All changes integrate cleanly with `uv`, the existing `Makefile`, and the existing CI workflows; no changes to feature code.

**Non-Goals:**
- Mutation testing. Investigated and explicitly removed from scope — see the "Mutation testing: deferred" decision below.
- 100% branch coverage. We set a realistic initial floor and a separate change can ratchet.
- Replacing pytest-cov with a different coverage tool.
- Migrating off Dependabot for any consumer that has already wired one up downstream — this template just won't ship one.

## Decisions

### Decision 1: Branch coverage as a separate floor, not a single number

Keep the existing `fail_under = 80` line-coverage floor in `pyproject.toml`. Add a separate **branch floor** enforced by the Makefile, parsed from `reports/coverage.json`'s `totals.percent_branches_covered`. The check is a private Make target (`check-branch-coverage`) that every coverage target invokes. The Makefile prints both numbers and fails on either.

**Why over alternative**: A single combined number hides whether a regression is "we stopped executing this code" vs. "we stopped asserting this branch arm." Two numbers preserve the signal. Reporting `--cov-branch` only and leaving the gate at 80% line would be cheaper but wouldn't actually enforce the new measurement.

### Decision 2: Route `make ci` through `make cov`, not `make test`

The existing `ci: quality test test-integration` chain never produced coverage data. Change to `ci: quality cov test-integration` and update the GitHub `tests` job (`.github/workflows/ci.yml`) from `run: make test` to `run: make cov`.

**Why**: this is the smallest change that makes the existing line floor (`fail_under = 80`) actually fire on every CI run, plus the new branch floor. The alternative (adding coverage as a separate Makefile target run after `test`) duplicates pytest invocations.

### Decision 3: Renovate over Dependabot, with explicit groups and SHA-pinned actions

Add `renovate.json` at repo root with:
- `extends: ["config:recommended", ":semanticCommits", ":dependencyDashboard"]`
- `packageRules` grouping: (a) `pytest` + `pytest-*`, (b) `fastapi` + `starlette` + `pydantic` + `pydantic-settings`, (c) `sqlmodel` + `sqlalchemy` + `alembic`, (d) `arq` + `redis` + `fakeredis`, (e) `boto3` + `botocore` + `boto3-stubs` + `moto`, (f) `dev-tooling` (`ruff`, `mypy`, `import-linter`, `pre-commit`, `pip-audit`).
- `lockFileMaintenance: { enabled: true, schedule: ["before 5am on monday"] }`
- `github-actions` manager with `pinDigests: true` so all `uses:` references are pinned to commit SHAs.
- `prConcurrentLimit: 5`, `prHourlyLimit: 2`.

Before enabling Renovate, rewrite every `uses: <action>@<version>` in `.github/workflows/*.yml` to `uses: <action>@<sha> # <version>` for the action SHAs that Renovate will subsequently maintain.

**Why over Dependabot**: Renovate's grouping is the killer feature — `fastapi`/`starlette`/`pydantic` move together, and Dependabot opens three PRs that conflict with each other on `uv.lock`. Dependabot's grouping support exists but is more limited and noisier for `uv` projects.

### Decision 4: Don't ratchet thresholds in this change

This change introduces the branch-coverage measurement, the gate, and a baseline floor. It deliberately does not bump existing thresholds beyond what the current code happens to pass. A later, separate change can ratchet once we have signal on whether tests are easily extendable to close gaps.

**Why**: Bundling "add the gate" with "raise the bar" makes the diff impossible to review honestly — every test added to satisfy a new threshold drowns the actual tooling change.

### Decision 5: Mutation testing — deferred to a follow-up change

Originally part of this proposal. After concrete investigation, removed from scope.

- **`mutmut 2.x`**: pinned `parso 0.8.7` cannot parse Python 3.10+ structural pattern matching (`match`/`case`) or PEP 695 `type` statements. The codebase's use cases pattern-match on `Result[T, E]` everywhere; `result.py` uses `type Result[T, E] = Ok[T] | Err[E]`. Mutmut 2.x aborts before generating mutants.
- **`mutmut 3.x`**: parses Python 3.12 fine, but its instrumentation injects a hardcoded assert (`assert not name.startswith('src.'), 'Failed trampoline hit. Module name starts with src., which is invalid'`) that rejects every mutated module in this repo. The assert exists because mutmut 3.x assumes the standard Python "src layout" — `src/` is on `PYTHONPATH` but is **not** itself a package — and this repo has `src/__init__.py`, making `src` a package and every import a `from src.X import Y`.

Making mutation testing work requires refactoring the repo to the standard src layout: delete `src/__init__.py`, add `src/` to `PYTHONPATH` (via `[tool.pytest.ini_options] pythonpath = ["src"]` or hatch build config), and rewrite **every** `from src.X import Y` import in the codebase. That touches every Python file, plus Alembic's `env.py`, FastAPI's entrypoint string, Docker's CMD, and the Import Linter contracts. Tracked as a separate `refactor-to-src-layout` change; once that lands, a follow-up can re-introduce `mutmut` cleanly.

**Why**: scope discipline. Mixing a tooling-add with a repo-wide refactor produces a diff that nobody can review honestly.

## Risks / Trade-offs

- **[Branch coverage exposes uncovered `Result`-error arms]** → Mitigation: set the initial branch floor to what the codebase actually achieves on day one (round down to the nearest 5%). A follow-up change can ratchet after we close the obvious gaps. We will **not** add test scaffolding to inflate the number in this change.
- **[Routing `ci` through `cov` instead of `test` means CI runtime grows by the cost of `--cov` instrumentation]** → Acceptable; pytest-cov overhead on this suite is ~2s. The existing `test` target is preserved for fast iteration without coverage.
- **[Renovate firehose on first activation]** → Mitigation: `prConcurrentLimit: 5` and `prHourlyLimit: 2`; the first batch is reviewed in a single sweep before tightening. Dependency Dashboard issue lets us defer or group ad-hoc.
- **[SHA-pinning actions hurts readability of workflow files]** → Mitigation: keep the `# v4.1.7`-style trailing comment that Renovate maintains so reviewers see semantic versions at a glance.
- **[A consumer fork of this template may already have its own Renovate / Dependabot]** → Acceptable: this is a starter template — consumers can delete `renovate.json` or merge configs. Documented in `docs/development.md`.

## Migration Plan

Single PR, no runtime changes, no DB migration. Order of operations:

1. Enable `--cov-branch` on every coverage target in the Makefile.
2. Add `BRANCH_COVERAGE_FLOOR` to the Makefile and a `check-branch-coverage` private target.
3. Re-route `ci:` and `ci-local:` through `cov:` so the coverage floors actually fire.
4. Update `.github/workflows/ci.yml` to call `make cov` instead of `make test`.
5. SHA-pin all `uses:` in `.github/workflows/*.yml`.
6. Add `renovate.json`. Renovate auto-onboards when its GitHub App is installed; if not installed, the file is inert and harmless.
7. Update `docs/development.md`, `README.md`, and `CLAUDE.md`.

**Rollback**: revert the PR. Nothing runtime depends on any of these.
