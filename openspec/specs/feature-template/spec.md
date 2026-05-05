# feature-template Specification

## Purpose
TBD - created by archiving change feature-template-and-docs. Update Purpose after archive.
## Requirements
### Requirement: Template package layout

`src/features/_template/` MUST exist and MUST mirror the canonical feature layout (`domain/`, `application/{ports/inbound,ports/outbound,commands,queries,contracts,errors,use_cases}/`, `adapters/{inbound/http,outbound/persistence}/`, `composition/`, `tests/`) with valid `__init__.py` files.

#### Scenario: Layout matches canonical
- **WHEN** the migration is complete
- **THEN** `src/features/_template/` contains every subdirectory listed above
- **AND** running `python -c "import src.features._template"` exits 0

### Requirement: Template package is inert at runtime

`src/features/_template/composition/wiring.py` MUST NOT be invoked from `src/main.py`. The template MUST NOT register routes, MUST NOT mount middleware, and MUST NOT alter the application's runtime behavior.

#### Scenario: No template routes registered
- **WHEN** the API starts
- **THEN** the OpenAPI document contains zero paths under `/api/_template/...` or any name derived from the template

### Requirement: Template passes all quality gates

`make check` (ruff + mypy + import-linter) MUST pass with the template present, and `pytest --collect-only` MUST report zero collection errors. Placeholders MUST use `pass` or trivial stubs that satisfy mypy strict.

#### Scenario: Template passes lint and types
- **WHEN** `make check` runs
- **THEN** the run succeeds with zero errors mentioning `src/features/_template/`

### Requirement: Template `README.md` recipe

`src/features/_template/README.md` MUST contain a numbered recipe that takes a developer from `cp -r src/features/_template src/features/<feature>` to a working feature with tests. The recipe MUST cover, in order: copy & rename, define domain aggregate, declare outbound ports, declare inbound Protocols, define commands/queries/contracts/errors, implement use cases, implement outbound adapters, implement inbound HTTP adapter, wire composition, register in `src/main.py`, write tests (domain → use cases → contracts → integration → e2e), run `make check && make test`. Each step MUST link to the equivalent file under `src/features/kanban/` as the worked example.

#### Scenario: All steps documented
- **WHEN** a developer reads the README from start to finish
- **THEN** they can add a new feature without consulting any other document beyond Kanban

### Requirement: Placeholder markers

Every placeholder in `src/features/_template/` MUST carry a `TODO(template):` marker so authors can locate every spot to edit with `rg "TODO\(template\):" src/features/<feature>`.

#### Scenario: Markers present
- **WHEN** `rg "TODO\(template\):" src/features/_template` runs
- **THEN** at least one match per placeholder file is reported
