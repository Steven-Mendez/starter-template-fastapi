# project-layout Specification

## Purpose
TBD - created by archiving change refactor-to-src-layout. Update Purpose after archive.
## Requirements
### Requirement: `src/` is a source root, not a package

The system SHALL place application code under `src/` and SHALL treat `src/` as a directory placed on `sys.path` rather than as an importable Python package. The file `src/__init__.py` SHALL NOT exist. Modules SHALL import each other by their real package names (`features.users.X`, `app_platform.config.settings`, `main`, `worker`) and SHALL NOT prefix any internal import with `src.`.

#### Scenario: No `__init__.py` at the source root

- **WHEN** an operator inspects the repository
- **THEN** no file `src/__init__.py` exists

#### Scenario: No internal import uses the `src.` prefix

- **WHEN** an operator runs `grep -rn "^[ ]*\\(from\\|import\\) src\\." --include="*.py" .` from the repository root
- **THEN** the command produces no matches in tracked source files

#### Scenario: `src/` is on the Python path for tests

- **WHEN** an operator inspects `pyproject.toml`
- **THEN** `[tool.pytest.ini_options]` declares `pythonpath = ["src"]` (or equivalent), and `pytest` resolves `import features.users.X` and `import app_platform.X` without further configuration

#### Scenario: `src/` is on the Python path for Alembic

- **WHEN** an operator inspects `alembic.ini`
- **THEN** `prepend_sys_path` includes `src`, and `alembic/env.py` imports its models and settings by their real names (no `src.` prefix)

### Requirement: `platform/` directory is renamed to `app_platform/`

The system SHALL NOT define a top-level package named `platform`, because that name shadows the Python standard library's `platform` module when the source root is first on `sys.path`. The directory previously at `src/platform/` SHALL be renamed to `src/app_platform/`, and every internal reference SHALL use the new name.

#### Scenario: Stdlib `platform` is reachable from application code

- **WHEN** an operator runs `PYTHONPATH=src python -c "import platform; print(platform.system())"` from the repository root
- **THEN** the command prints the host operating system name (i.e. resolves to the standard library, not to a project directory)

#### Scenario: No internal import references `platform` as a top-level package

- **WHEN** an operator runs `grep -rn "^[ ]*\\(from\\|import\\) platform\\b" --include="*.py" src/` from the repository root
- **THEN** the command produces no matches (the project's own modules import `app_platform`, never `platform`)

#### Scenario: No internal import references `src.platform`

- **WHEN** an operator runs `grep -rn "src\\.platform" --include="*.py" --include="*.toml" --include="*.ini" --include="*.yml" --include="*.yaml" --include="Makefile" --include="Dockerfile*" .` from the repository root
- **THEN** the command produces no matches in tracked files

### Requirement: Entrypoints reference modules by their real names

The system SHALL configure every entrypoint — FastAPI CLI, `uvicorn`, the Docker image, the Makefile, and the Alembic environment — to import modules by their post-refactor names (`main:app`, `worker`, `app_platform.X`, `features.X`) and SHALL NOT use the `src.` prefix.

#### Scenario: FastAPI CLI entrypoint declares the bare module

- **WHEN** an operator inspects `pyproject.toml`
- **THEN** `[tool.fastapi]` declares `entrypoint = "main:app"` (no `src.` prefix)

#### Scenario: Docker image runs uvicorn against the bare module

- **WHEN** an operator inspects `Dockerfile`
- **THEN** every `CMD` that invokes `uvicorn` references `main:app` (not `src.main:app`), and the image either sets `ENV PYTHONPATH=src` or invokes uvicorn with `--app-dir src`

#### Scenario: Makefile invokes the worker by its bare module name

- **WHEN** an operator inspects `Makefile`
- **THEN** the `worker` target invokes `python -m worker` (not `python -m src.worker`), and the `outbox-retry-failed` target invokes `python -m features.outbox.management` with `PYTHONPATH=src` set in the environment

#### Scenario: Alembic env imports models by their real names

- **WHEN** an operator inspects `alembic/env.py`
- **THEN** every model import references `features.X.adapters.outbound.persistence.sqlmodel.models` or `app_platform.persistence.sqlmodel.authorization.models` (no `src.` prefix), and the settings import is `from app_platform.config.settings import AppSettings`

### Requirement: Architecture contracts reference modules by their real names

The system SHALL define every Import Linter contract in `pyproject.toml` using post-refactor module names (`features.X`, `app_platform.X`, `main`, `worker`) and SHALL NOT reference any module via the `src.` prefix. Every contract's intent (which layers may import which) SHALL be preserved exactly.

#### Scenario: No Import Linter contract path uses `src.`

- **WHEN** an operator inspects the `[tool.importlinter]` section of `pyproject.toml`
- **THEN** no `source_modules`, `forbidden_modules`, `allowed_modules`, or `layers` entry contains the string `src.`

#### Scenario: Architecture contracts pass after the refactor

- **WHEN** an operator runs `make lint-arch` on a tree where the refactor has been applied
- **THEN** Import Linter reports every contract as kept, with no broken contracts

#### Scenario: The `platform` → `features` rule is renamed

- **WHEN** an operator inspects the Import Linter contract that previously forbade `src.platform` from importing `src.features`
- **THEN** the contract now forbids `app_platform` from importing `features`, and the existing exception for `app_platform.config.settings` still permits it to import each feature's `composition.settings` module

### Requirement: Documentation reflects the new layout

The system SHALL update `CLAUDE.md`, `README.md`, and any `docs/*.md` file that names internal modules to use post-refactor names (no `src.` prefix; `app_platform` rather than `platform` when referring to the project directory).

#### Scenario: CLAUDE.md commands and module map use the new names

- **WHEN** a contributor reads `CLAUDE.md`
- **THEN** every code reference to an internal module (e.g. `src/platform/config/settings.py`, `src.main:app`, `python -m src.worker`) has been rewritten to use `src/app_platform/...`, `main:app`, and `python -m worker` respectively

#### Scenario: README and docs prose drop the `src.` prefix

- **WHEN** a contributor reads `README.md` or any file under `docs/`
- **THEN** no prose, command example, or import snippet uses `src.` as a Python import prefix; references to the source directory on disk (`src/`) remain unchanged

### Requirement: Destructive migrations raise on downgrade and are scanned in CI

Migrations whose `upgrade()` performs destructive operations (column drops, table drops, index drops, or `op.execute` running a `DROP` / `ALTER TABLE ... DROP`) SHALL have a `downgrade()` whose first executable statement is `raise NotImplementedError("...")` and whose message references `docs/operations.md#migration-policy`. Narrowing `alter_column` (e.g., `String(length=255)` → `String(length=64)`) is destructive but cannot be detected statically; operators MUST opt in by hand to the same convention.

The policy SHALL be documented in `docs/operations.md`. The project SHALL ship a `make migrations-check` pytest scanner that walks `alembic/versions/*.py` and fails when a destructive operation is found without either a raising `downgrade()` or an inline `# allow: destructive` comment **on the same line as the destructive call**. `make ci` SHALL invoke `make migrations-check`.

#### Scenario: Existing column-drop migration refuses to downgrade

- **GIVEN** the migration `20260513_0010_drop_users_password_hash`
- **WHEN** an operator runs `alembic downgrade -1`
- **THEN** the operation raises `NotImplementedError`
- **AND** the error message references `docs/operations.md#migration-policy`

#### Scenario: Scanner accepts a compliant destructive migration

- **GIVEN** a migration whose `upgrade()` calls `op.drop_column("foo", "bar")` and whose `downgrade()` body is `raise NotImplementedError("...")`
- **WHEN** `make migrations-check` runs
- **THEN** the command exits 0

#### Scenario: Scanner rejects a non-compliant destructive migration

- **GIVEN** a migration whose `upgrade()` calls `op.drop_column("foo", "bar")` and whose `downgrade()` body is `pass`
- **WHEN** `make migrations-check` runs
- **THEN** the command exits non-zero
- **AND** the failure message names the offending file and line

#### Scenario: Scanner respects the inline override

- **GIVEN** a migration whose `upgrade()` contains `op.drop_index("idx_foo")  # allow: destructive` and whose `downgrade()` recreates the index normally
- **WHEN** `make migrations-check` runs
- **THEN** the command exits 0

#### Scenario: Scanner detects raw-SQL drops

- **GIVEN** a migration whose `upgrade()` calls `op.execute("DROP TABLE foo")` and whose `downgrade()` body is `pass`
- **WHEN** `make migrations-check` runs
- **THEN** the command exits non-zero

#### Scenario: CI gate enforces the policy

- **WHEN** a developer opens a PR adding a non-compliant destructive migration
- **THEN** `make ci` fails on the `migrations-check` step
- **AND** the failure surfaces in the GitHub Actions logs before any deploy

#### Scenario: Irreversible migration attempted downgrade aborts loudly

- **GIVEN** a destructive migration whose `downgrade()` raises `NotImplementedError("... see docs/operations.md#migration-policy")`
- **WHEN** an operator runs `uv run alembic downgrade -1` against that revision
- **THEN** the command aborts with a `NotImplementedError` whose message references `docs/operations.md#migration-policy`
- **AND** no schema change is applied (the prior `upgrade` state remains)
- **AND** no data is silently re-introduced under a default value

### Requirement: arq worker has bounded result retention with per-handler override

`WorkerSettings` SHALL set `max_jobs` and `job_timeout` from configured values (defaults: 16 and 600 seconds). Each handler's `keep_result` SHALL default to `keep_result_seconds_default` (300) and SHALL be overridable per-handler via an explicit `keep_result_seconds` argument at registration time. The platform default SHALL be configurable via `APP_JOBS_KEEP_RESULT_SECONDS_DEFAULT`. `docs/background-jobs.md` SHALL document the recommended Redis eviction policy (`maxmemory-policy allkeys-lru`).

#### Scenario: Handler without override picks the platform default

- **GIVEN** a handler registered with `JobHandlerRegistry.register("send_email", handler)` (no `keep_result_seconds` argument)
- **WHEN** the worker boots
- **THEN** the arq `Function` for `send_email` has `keep_result == 300`

#### Scenario: Handler with explicit override picks the override value

- **GIVEN** a handler registered with `JobHandlerRegistry.register("billing_charge", handler, keep_result_seconds=86400)`
- **WHEN** the worker boots
- **THEN** the arq `Function` for `billing_charge` has `keep_result == 86400`

#### Scenario: Settings override the platform default

- **GIVEN** `APP_JOBS_KEEP_RESULT_SECONDS_DEFAULT=600`
- **WHEN** the worker boots
- **THEN** every handler without an explicit override has `Function.keep_result == 600`

#### Scenario: max_jobs and job_timeout flow into WorkerSettings

- **GIVEN** `APP_JOBS_MAX_JOBS=32` and `APP_JOBS_JOB_TIMEOUT_SECONDS=900`
- **WHEN** the worker boots
- **THEN** `WorkerSettings.max_jobs == 32` and `WorkerSettings.job_timeout == 900`

#### Scenario: Handler exceeding job_timeout is cancelled

- **GIVEN** a handler registered with the default `job_timeout_seconds=600`
- **WHEN** an enqueued invocation runs for more than 600 seconds
- **THEN** arq cancels the task and records a failure
- **AND** the worker process remains available to pick up the next job (not pinned by the hung handler)
