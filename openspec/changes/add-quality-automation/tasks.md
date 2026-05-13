## 1. Baseline measurement

- [x] 1.1 Run `make cov` on a clean `main` checkout (with `--cov-branch` patched in) and capture the line and branch percentages. **Result**: line 88.68%, branch 63.27%. Confirmed: `make cov` previously invoked pytest-cov without `--cov-branch`, so the configured `branch = true` in pyproject was silently ignored end-to-end, and the existing `make ci` ran `make test` (no `--cov` at all), so the 80% line floor was never enforced in CI.
- [x] 1.2 Round the captured branch percentage down to the nearest 5% → **`BRANCH_COVERAGE_FLOOR = 60`**.

## 2. Branch-coverage gate

- [x] 2.1 Add comments in `pyproject.toml` documenting that `[tool.coverage.run] branch = true` requires `--cov-branch` at invocation time, and that the branch floor is enforced by the Makefile (not by `coverage.report.fail_under`, which only gates the combined number).
- [x] 2.2 Add `--cov-branch` and `--cov-report=json:reports/coverage.json` to `cov`, `cov-html`, and `cov-xml` in the `Makefile`. Add a private `check-branch-coverage` target that parses `reports/coverage.json` and fails if `totals.percent_branches_covered < BRANCH_COVERAGE_FLOOR`. Wire every coverage target to call it after `pytest`.
- [x] 2.3 Add `BRANCH_COVERAGE_FLOOR ?= 60` near the top of the `Makefile`, overrideable via env.
- [x] 2.4 Route `ci:` and `ci-local:` through `cov` instead of `test` so both the line and branch floors actually fire on every CI run.
- [x] 2.5 Update `.github/workflows/ci.yml` `tests` job from `run: make test` to `run: make cov`.
- [x] 2.6 Verify both gates: `make cov` passes at 85% line / 62.18% branch (above 60% floor); `BRANCH_COVERAGE_FLOOR=95 make check-branch-coverage` fails as designed.

## 3. SHA-pin existing GitHub Actions

- [x] 3.1 Enumerate every `uses:` reference in `.github/workflows/*.yml`. Found: `actions/checkout@v4`, `astral-sh/setup-uv@v6`, `gitleaks/gitleaks-action@v2` in `ci.yml`. `setup-repo.yml` has zero `uses:` lines.
- [x] 3.2 Resolve each tag to a full 40-char commit SHA via `gh api`:
  - `actions/checkout@v4` → `34e114876b0b11c390a56381ad16ebd13914f8d5`
  - `astral-sh/setup-uv@v6` → `d0cc045d04ccac9d8b7881df0226f9e82c39688e` (annotated tag dereferenced)
  - `gitleaks/gitleaks-action@v2` → `ff98106e4c7b2bc287b24eaf42907196329070c7` (annotated tag dereferenced)
- [x] 3.3 Rewrite each `uses:` line as `uses: <owner>/<repo>@<sha> # <original-tag>` in `ci.yml`. Semantic versions unchanged — only pinned.

## 4. Renovate config

- [x] 4.1 Create `renovate.json` at repo root with `$schema`, `extends: ["config:recommended", ":semanticCommits", ":dependencyDashboard"]`, `timezone: "Etc/UTC"`, `prConcurrentLimit: 5`, `prHourlyLimit: 2`.
- [x] 4.2 Declare `packageRules` groups: `pytest` + `pytest-*`, `fastapi-pydantic` (`fastapi` + `starlette` + `pydantic` + `pydantic-settings`), `sqlmodel-stack` (`sqlmodel` + `sqlalchemy` + `alembic`), `arq-redis` (`arq` + `redis` + `fakeredis`), `boto3` (`boto3` + `botocore` + `boto3-stubs` + `moto`), `dev-tooling` (`ruff` + `mypy` + `import-linter` + `pre-commit` + `pip-audit`).
- [x] 4.3 Enable `lockFileMaintenance: { enabled: true, schedule: ["before 5am on monday"] }`.
- [x] 4.4 Enable the top-level `github-actions` manager with `pinDigests: true` so Renovate maintains the SHAs added in section 3; redundant `packageRules` entry for `matchManagers: ["github-actions"]` with `pinDigests: true` for clarity.
- [x] 4.5 Confirm `.github/dependabot.yml` does not exist.
- [x] 4.6 Validate `renovate.json` parses. **Partial**: `npx --yes renovate-config-validator` was denied by harness permissions; fell back to a JSON-parse check via `python -c`, which succeeds. Renovate will surface any schema issues on first run.

## 5. Documentation

- [x] 5.1 Add a "Quality Gates" section to `docs/development.md` describing the dual line/branch coverage gate (with the actual numbers), how `BRANCH_COVERAGE_FLOOR` is calibrated, and how to override it.
- [x] 5.2 Add a "Dependency Updates" section to `docs/development.md` explaining Renovate's grouped PR cadence, weekly lockfile maintenance, Dependency Dashboard issue, and SHA-pinning convention.
- [x] 5.3 Update `README.md`: brief mention of the dual coverage floors under quality/testing; link to `docs/development.md` for detail; update the Commands table.
- [x] 5.4 Update `CLAUDE.md`: Commands table reflects new `make cov` behavior; Testing strategy section updates the "Coverage gate" sentence to name both floors.

## 6. Mutation testing — explicitly out of scope

- [x] 6.1 Investigation: tried `mutmut 2.4.4` / `2.5.1` (pinned `parso 0.8.7` can't parse `match`/`case` or PEP 695 `type` statements — aborts on `result.py` and every use-case file). Tried `mutmut 3.5.0` (parses Python 3.12 fine, but its trampoline injects `assert not name.startswith('src.'), ...`, which rejects every mutated module in this repo because `src/__init__.py` exists). Confirmed root cause: the repo uses a `src.X` import layout, whereas mutmut hardcodes the standard Python "src layout" (no `src/__init__.py`, imports without the `src.` prefix). Making mutmut work requires a repo-wide refactor of every import — out of scope here.
- [x] 6.2 Remove `mutmut` from dev deps, drop `[tool.mutmut]` from `pyproject.toml`, drop the `make mutation` Make target, delete `.github/workflows/mutation.yml`, clean mutmut entries from `.gitignore`, and remove mutation-testing references from `docs/development.md`, `README.md`, `CLAUDE.md`, and these openspec artifacts.
- [ ] 6.3 **Follow-up**: open a separate `refactor-to-src-layout` change to delete `src/__init__.py`, put `src/` on `PYTHONPATH`, rewrite every `from src.X import Y` import in the codebase, and update Alembic/FastAPI/Docker entrypoints. Once that lands, a follow-up to re-introduce `mutmut` becomes a 5-minute change. Tracked outside this change.

## 7. Verify and ship

- [x] 7.1 Run `make cov` → passes; line 85.00%, branch 62.18% (above 60% floor), 311 tests pass, no warnings.
- [x] 7.2 Run `make typecheck` → passes; 377 files, no issues.
- [x] 7.3 Run `make lint-arch` → passes; 19 contracts kept, 0 broken.
- [x] 7.4 Run `make lint` → fails on `src/features/outbox/adapters/outbound/sqlmodel/models.py:64` (E501 line too long, 89 > 88). **Not caused by this change** — it is preexisting working-tree state from the parallel `add-outbox-pattern` change. This change does not include outbox files in its commit.
- [ ] 7.5 **Deferred to user**: push branch, open PR, confirm `ci.yml` is green with SHA-pinned actions and the new branch-coverage gate. If the Renovate GitHub App is not installed on the repo, note in the PR description that `renovate.json` is inert until the App is added.
