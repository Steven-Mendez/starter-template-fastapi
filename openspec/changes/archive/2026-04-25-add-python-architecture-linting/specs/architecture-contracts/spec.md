# Spec: Hexagonal Architecture Import Contracts

**Capability**: architecture-contracts
**Change**: add-python-architecture-linting

---

## ADDED Requirements

### Requirement: AC-01 — Import Linter contracts are defined in `pyproject.toml` and enforce inward dependency direction


**Priority**: High

Five Import Linter contracts MUST be declared in `pyproject.toml` covering the four hexagonal layers and the core inward dependency rule. Every contract MUST include a comment referencing the `hex-design-guide.md` section that justifies it.

**Acceptance Criteria**:
1. `[tool.importlinter]` section exists in `pyproject.toml` with `root_packages = ["src"]` and `include_external_packages = true`.
2. Five contracts are defined: Domain isolation, Application isolation, API restrictions, Infrastructure restrictions, Inward layers direction.
3. Each contract has a `name` field that is human-readable and describes the constraint.
4. `uv run lint-imports` exits 0 on the clean codebase.
5. `uv run lint-imports` exits non-zero when a contract is violated, identifying the offending module and violated contract by name.

#### Scenario: All contracts pass on clean codebase

- Given: the project with all OpenSpec changes applied
- When: `uv run lint-imports` is executed
- Then: exit code is 0
- And: output shows each contract name with status `KEPT`

#### Scenario: Domain importing infrastructure is detected

- Given: `src/domain/kanban/models/board.py` contains `from sqlalchemy import Column`
- When: `uv run lint-imports` is executed
- Then: exit code is non-zero
- And: output contains `Domain layer: no outward or framework dependencies` contract name
- And: output identifies `src.domain.kanban.models.board` as the source module
- And: output identifies `sqlalchemy` as the forbidden import

### Requirement: AC-02 — Domain layer is forbidden from importing framework and infrastructure libraries


**Priority**: Critical

Contract 1 (`"Domain layer: no outward or framework dependencies"`) MUST enumerate all framework and infrastructure libraries that are forbidden from the domain layer, per `hex-design-guide.md` §3.

**Acceptance Criteria**:
1. Contract 1 forbids: `src.application`, `src.api`, `src.infrastructure`, `src.config`.
2. Contract 1 forbids external libraries: `fastapi`, `starlette`, `sqlmodel`, `sqlalchemy`, `uvicorn`, `httpx`, `alembic`, `pydantic_settings`, `psycopg`.
3. Importing any of the above from `src.domain.*` causes `uv run lint-imports` to fail with a named violation.
4. `src.domain.*` importing from Python standard library (e.g., `dataclasses`, `datetime`, `uuid`, `enum`, `typing`) does NOT trigger a violation.

#### Scenario: `fastapi` import in domain is caught

- Given: `src/domain/kanban/models/card.py` adds `from fastapi import HTTPException`
- When: `uv run lint-imports` runs
- Then: exit code is non-zero
- And: output names `Contract 1` or its name string
- And: output names `fastapi` as the forbidden module

#### Scenario: Standard library imports in domain are permitted

- Given: `src/domain/kanban/models/board.py` imports `from dataclasses import dataclass, field`
- When: `uv run lint-imports` runs
- Then: Contract 1 does not flag `dataclasses`
- And: exit code is 0 (assuming no other violations)

### Requirement: AC-03 — Application layer is forbidden from importing infrastructure libraries and framework types


**Priority**: Critical

Contract 2 (`"Application layer: no infrastructure or framework dependencies"`) enforces `hex-design-guide.md` §4 and §29 Rule 2: use cases MUST not directly depend on SQLAlchemy, FastAPI, httpx, or other infrastructure libraries.

**Acceptance Criteria**:
1. Contract 2 forbids: `src.api`, `src.infrastructure`, `src.config`.
2. Contract 2 forbids: `fastapi`, `starlette`, `sqlmodel`, `sqlalchemy`, `uvicorn`, `httpx`, `alembic`, `pydantic_settings`, `psycopg`.
3. `pydantic` is NOT in the forbidden list (allowed per hex-design-guide.md §35 for application DTOs).
4. Importing `sqlmodel` or `fastapi` from any `src.application.*` module causes `uv run lint-imports` to fail.
5. `src.application.*` importing from `src.domain.*` does NOT trigger Contract 2.

#### Scenario: `sqlmodel` in application is caught

- Given: `src/application/commands/handlers.py` adds `from sqlmodel import Session`
- When: `uv run lint-imports` runs
- Then: exit code is non-zero
- And: output names Contract 2 or its name string
- And: output names `sqlmodel` as the forbidden module

#### Scenario: Domain import from application is permitted

- Given: `src/application/contracts/mappers.py` imports `from src.domain.kanban.models import Board`
- When: `uv run lint-imports` runs
- Then: Contract 2 does not flag this import
- And: exit code remains 0 (assuming no other violations)

### Requirement: AC-04 — API adapter may not directly access infrastructure or domain modules

The system MUST satisfy this requirement as specified below.


**Priority**: High

Contract 3 (`"API adapter: no infrastructure bypass or direct domain access"`) ensures the API adapter layer only uses the application layer as its interface — it does not shortcut to infrastructure or domain.

**Acceptance Criteria**:
1. Contract 3 forbids `src.infrastructure` from `src.api.*`.
2. Contract 3 forbids `src.domain` from `src.api.*`.
3. Contract 3 forbids `sqlmodel`, `sqlalchemy`, `alembic`, `uvicorn`, `psycopg` from `src.api.*`.
4. `src.api.*` importing from `src.application.*` does NOT trigger Contract 3.
5. `src.api.*` importing `fastapi` and `pydantic` does NOT trigger Contract 3 (these are the API adapter's own tools).

#### Scenario: API importing from infrastructure is caught

- Given: `src/api/routers/boards.py` adds `from src.infrastructure.persistence.sqlmodel_repository import SQLModelKanbanRepository`
- When: `uv run lint-imports` runs
- Then: exit code is non-zero
- And: Contract 3 is named in the output

#### Scenario: API importing from application is permitted

- Given: `src/api/routers/boards.py` imports `from src.application.commands import CreateBoardCommand`
- When: `uv run lint-imports` runs
- Then: Contract 3 does not flag this import

### Requirement: AC-05 — Infrastructure layer may not import from the API adapter layer

The system MUST satisfy this requirement as specified below.


**Priority**: High

Contract 4 (`"Infrastructure: no inbound adapter imports"`) prevents outbound adapters from acquiring dependencies on the inbound adapter — which would create a dependency cycle with no path inward.

**Acceptance Criteria**:
1. Contract 4 forbids `src.api` from `src.infrastructure.*`.
2. `src.infrastructure.*` importing `src.application.*` (ports, contracts) does NOT trigger Contract 4.
3. `src.infrastructure.*` importing `src.domain.*` (entities, value objects) does NOT trigger Contract 4.
4. `src.infrastructure.*` importing `sqlmodel`, `sqlalchemy`, `httpx` does NOT trigger Contract 4.

#### Scenario: Infrastructure importing from API is caught

- Given: `src/infrastructure/persistence/sqlmodel_repository.py` adds `from src.api.dependencies import get_app_container`
- When: `uv run lint-imports` runs
- Then: exit code is non-zero
- And: Contract 4 is named in the output

### Requirement: AC-06 — `make lint-arch` is the canonical command for architecture contract verification

The system MUST satisfy this requirement as specified below.


**Priority**: High

A dedicated `lint-arch` Makefile target runs Import Linter and is integrated into `make check` so developers have a single command to verify all lint rules including architecture contracts.

**Acceptance Criteria**:
1. `make lint-arch` runs `uv run lint-imports`.
2. `make lint-arch` exits 0 on clean code and non-zero on violations.
3. `make check` runs `lint`, `lint-arch`, and `typecheck` in sequence.
4. `make help` lists `lint-arch` with a description.

#### Scenario: `make check` catches architecture violation alongside style lint

- Given: `src/application/commands/handlers.py` contains `import sqlalchemy`
- When: `make check` is executed
- Then: the `lint-arch` step fails before `typecheck` runs
- And: the output identifies the violated contract

### Requirement: AC-07 — Pytest boundary checker validates external library forbidden imports

The system MUST satisfy this requirement as specified below.


**Priority**: High

The existing `test_hexagonal_boundaries.py` is enhanced with `test_forbidden_external_library_imports` to cover external library checks at test time (complementing Import Linter's lint-time check). Both tools are required — Import Linter for fast lint-time feedback, pytest for structural/behavioral rules Import Linter cannot express.

**Acceptance Criteria**:
1. `test_forbidden_external_library_imports` exists in `tests/unit/test_hexagonal_boundaries.py`.
2. The test fails if any `src.domain.*` module imports from `fastapi`, `starlette`, `sqlmodel`, `sqlalchemy`, `uvicorn`, `httpx`, `alembic`, `pydantic_settings`, or `psycopg`.
3. The test fails if any `src.application.*` module imports the same libraries.
4. The test fails if `src.api.*` imports `sqlmodel`, `sqlalchemy`, `alembic`, `uvicorn`, or `psycopg`.
5. The test produces a violation message naming the source module and forbidden library.

#### Scenario: pytest catches `sqlalchemy` in domain

- Given: `src/domain/kanban/models/card.py` contains `import sqlalchemy`
- When: `pytest tests/unit/test_hexagonal_boundaries.py::test_forbidden_external_library_imports -v`
- Then: the test fails
- And: the failure message contains `src.domain.kanban.models.card imports sqlalchemy`

#### Scenario: pytest permits `pydantic` in application

- Given: `src/application/contracts/kanban.py` imports `from pydantic import BaseModel` (hypothetical)
- When: `pytest tests/unit/test_hexagonal_boundaries.py::test_forbidden_external_library_imports -v`
- Then: the test does NOT fail for this import
- And: `pydantic` is not in the application layer deny list

### Requirement: AC-08 — All contract exceptions are explicit, documented, and justified


**Priority**: Medium

Any `ignore_imports` entry in Import Linter contracts MUST include a comment that identifies the specific violation, the reason for the exception, and the OpenSpec change (if any) that will remove it.

**Acceptance Criteria**:
1. Every `ignore_imports` entry in `pyproject.toml` has a corresponding inline comment.
2. Temporary exceptions reference the OpenSpec change that will remove them (e.g., `# TODO: remove after relocate-ports-to-application-layer`).
3. Permanent exceptions reference the architectural justification (e.g., `# composition root: wires adapters by design`).
4. The number of `ignore_imports` entries is zero on a fully-refactored codebase (after all OpenSpec changes are applied).

#### Scenario: Linter passes after all OpenSpec changes are applied with no exceptions

- Given: all ten OpenSpec architecture changes have been implemented
- When: `uv run lint-imports` is executed
- Then: no `ignore_imports` entries exist in any contract
- And: exit code is 0
