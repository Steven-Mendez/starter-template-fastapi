# Spec: Hexagonal Boundary — Port Location

**Capability**: hexagonal-boundaries
**Change**: relocate-ports-to-application-layer

---

## ADDED Requirements

### Requirement: HB-PORT-01 — Repository port protocols live in the application layer


**Priority**: Critical

Repository port Protocols that define what the application needs from persistence MUST be declared under `src/application/ports/`. No file under `src/domain/` may define a Protocol class with `Repository` or `Port` in its name.

**Acceptance Criteria**:
1. `src/application/ports/kanban_command_repository.py` exists and contains `KanbanCommandRepositoryPort`.
2. `src/application/ports/kanban_query_repository.py` exists and contains `KanbanQueryRepositoryPort`.
3. `src/application/ports/kanban_repository.py` exists and contains `KanbanRepositoryPort`.
4. `src/domain/kanban/repository/` directory does not exist.
5. The architecture boundary test asserts criterion 4 and passes.

#### Scenario: Application layer exports its own port contracts

- Given: the project is installed and importable
- When: `from src.application.ports import KanbanCommandRepositoryPort, KanbanQueryRepositoryPort` is executed
- Then: both names resolve to Protocol classes without error

#### Scenario: Domain module does not expose repository interfaces

- Given: the project source tree
- When: `src/domain/kanban/repository/` is inspected
- Then: the directory does not exist

### Requirement: HB-PORT-04 — Architecture test asserts domain does not contain port modules


**Priority**: High

A new test in `tests/unit/test_hexagonal_boundaries.py` MUST verify at the file-system level that no port Protocol files exist inside `src/domain/`.

**Acceptance Criteria**:
1. `test_domain_does_not_contain_port_modules` function exists in `test_hexagonal_boundaries.py`.
2. The test asserts `src/domain/kanban/repository/` does not exist as a directory.
3. The test passes after relocation is complete.

#### Scenario: Boundary test catches accidental re-introduction of domain ports

- Given: `test_hexagonal_boundaries.py` contains `test_domain_does_not_contain_port_modules`
- When: a developer accidentally creates `src/domain/kanban/repository/command.py`
- Then: the test fails with a message indicating ports MUST live in `src/application/ports/`

### Requirement: HB-PORT-05 — `DENY_MATRIX` blocks `src.domain.kanban.repository` in all layers after deletion


**Priority**: High

After the domain repository directory is deleted, the `DENY_MATRIX` in `test_hexagonal_boundaries.py` MUST be updated to deny any future import of `src.domain.kanban.repository` from all layers. This prevents the directory from being recreated and silently breaking the architecture.

**Acceptance Criteria**:
1. `"src.domain.kanban.repository"` appears in `DENY_MATRIX["domain"]`, `DENY_MATRIX["application"]`, `DENY_MATRIX["api"]`, and `DENY_MATRIX["infrastructure"]`.
2. `TRANSITIVE_DENY_MATRIX` is updated similarly.
3. If any module imports from `src.domain.kanban.repository`, `test_hexagonal_architecture_boundaries` fails with a violation diagnostic.

#### Scenario: DENY_MATRIX catches re-introduction of a domain port import

- Given: `DENY_MATRIX` includes `"src.domain.kanban.repository"` in all layer deny lists
- When: a developer adds `from src.domain.kanban.repository import X` to any production module
- Then: `test_hexagonal_architecture_boundaries()` fails, identifying the violating module and import

## ADDED Requirements

### Requirement: HB-PORT-02 — Infrastructure adapters import ports from application layer


**Priority**: Critical

`src/infrastructure/persistence/sqlmodel_repository.py` and `src/infrastructure/persistence/in_memory_repository.py` MUST import repository port protocols from `src.application.ports`, not from `src.domain`.

**Acceptance Criteria**:
1. No `from src.domain.kanban.repository` import appears in any file under `src/infrastructure/`.
2. Both adapter files import `KanbanRepositoryPort` from `src.application.ports.kanban_repository`.
3. The architecture boundary test `test_hexagonal_architecture_boundaries` passes.

#### Scenario: Infrastructure adapter resolves port through application namespace

- Given: `src/infrastructure/persistence/sqlmodel_repository.py` source
- When: its import statements are inspected
- Then: the repository port import is `from src.application.ports.kanban_repository import KanbanRepositoryPort`
- And: no import from `src.domain.kanban.repository` is present

### Requirement: HB-PORT-03 — Application UnitOfWork protocol imports from application ports


**Priority**: High

`src/application/shared/unit_of_work.py` declares the `kanban` field typed as `KanbanCommandRepositoryPort`. After this change that import MUST come from `src.application.ports`, not `src.domain`.

**Acceptance Criteria**:
1. `src/application/shared/unit_of_work.py` imports `KanbanCommandRepositoryPort` from `src.application.ports.kanban_command_repository`.
2. No `src.domain.kanban.repository` import appears in any file under `src/application/`.

#### Scenario: UnitOfWork port field resolves to application-owned protocol

- Given: the UnitOfWork Protocol definition
- When: the type annotation of the `kanban` attribute is inspected
- Then: it resolves to `KanbanCommandRepositoryPort` from `src.application.ports`
