## ADDED Requirements

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
