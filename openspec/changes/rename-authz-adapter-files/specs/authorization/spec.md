## ADDED Requirements

### Requirement: Adapter classes live in `adapter.py` (not `repository.py`) when so named

`src/features/authorization/adapters/outbound/sqlmodel/adapter.py` SHALL be the module that contains `SQLModelAuthorizationAdapter` and `SessionSQLModelAuthorizationAdapter`. No file named `repository.py` SHALL exist in `src/features/authorization/adapters/outbound/sqlmodel/`. Every import targeting the engine-owning or session-scoped authorization adapter SHALL resolve through the `adapter` module path.

#### Scenario: File exists with the new name

- **GIVEN** a fresh checkout of the repository
- **WHEN** an inspection lists `src/features/authorization/adapters/outbound/sqlmodel/`
- **THEN** `adapter.py` exists
- **AND** `repository.py` does NOT exist

#### Scenario: No import resolves through the old module path

- **GIVEN** the repository after the rename
- **WHEN** the tree is searched for the substring `authorization.adapters.outbound.sqlmodel.repository`
- **THEN** zero source files contain that substring
- **AND** zero test files contain that substring

#### Scenario: Quality gates pass after the rename

- **GIVEN** the rename and import updates have been applied
- **WHEN** `make lint`, `make lint-arch`, `make typecheck`, and `make ci` are run
- **THEN** every gate passes
- **AND** Import Linter reports no new contract violations
