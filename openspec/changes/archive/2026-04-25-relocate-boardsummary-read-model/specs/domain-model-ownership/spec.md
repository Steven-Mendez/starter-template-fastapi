# Spec: Domain Model Ownership — BoardSummary

**Capability**: domain-model-ownership
**Change**: relocate-boardsummary-read-model

---

## ADDED Requirements

### Requirement: DMO-04 — Architecture test asserts `BoardSummary` absent from domain models

The system MUST satisfy this requirement as specified below.


**Priority**: Low

A file-system level assertion prevents re-introduction of projection types into the domain.

**Acceptance Criteria**:
1. `test_hexagonal_boundaries.py` contains a test (or assertion within an existing test) that `src/domain/kanban/models/board_summary.py` does not exist.
2. The test fails if the file is re-introduced.

#### Scenario: Boundary test catches accidental re-introduction of domain projections

- Given: `test_hexagonal_boundaries.py` contains `test_domain_does_not_contain_projection_types`
- When: a developer creates `src/domain/kanban/models/board_summary.py`
- Then: the test fails with a message explaining projection types belong in `src/application/contracts/`

## ADDED Requirements

### Requirement: DMO-02 — `KanbanQueryRepositoryPort.list_all()` returns `list[AppBoardSummary]`


**Priority**: Medium

The query repository port MUST return the application-layer DTO directly. No intermediate domain projection type is needed.

**Acceptance Criteria**:
1. `KanbanQueryRepositoryPort.list_all()` return type is `list[AppBoardSummary]`.
2. `AppBoardSummary` is imported in the port from `src.application.contracts`.
3. Both `InMemoryKanbanRepository` and `SQLModelKanbanRepository` return `list[AppBoardSummary]` from `list_all()`.
4. The port method can be called and returns populated results for a non-empty repository.

#### Scenario: Repository returns `AppBoardSummary` directly

- Given: an `InMemoryKanbanRepository` with one board saved
- When: `repository.list_all()` is called
- Then: the result is a `list[AppBoardSummary]` with one element
- And: the element has the same `id`, `title`, `created_at` as the saved board

## ADDED Requirements

### Requirement: DMO-01 — `BoardSummary` does not exist in the domain layer


**Priority**: Medium

`BoardSummary` is a read model projection (a DTO shaped by a SELECT query), not a domain entity or value object. It MUST not exist in `src/domain/kanban/models/`.

**Acceptance Criteria**:
1. `src/domain/kanban/models/board_summary.py` does not exist.
2. `BoardSummary` is not exported from `src.domain.kanban.models`.
3. No file under `src/` imports `BoardSummary` from `src.domain.kanban.models`.
4. The architecture boundary test passes without any exemption related to `BoardSummary`.

#### Scenario: Domain models package does not export `BoardSummary`

- Given: the project source tree
- When: `from src.domain.kanban.models import BoardSummary` is attempted
- Then: `ImportError` is raised

### Requirement: DMO-03 — `to_app_board_summary` mapper function does not exist

The system MUST satisfy this requirement as specified below.


**Priority**: Medium

The mapper `to_app_board_summary(summary: BoardSummary) -> AppBoardSummary` was a no-op copy between two identical types. After this change, the repository returns `AppBoardSummary` directly, eliminating the need for the mapper.

**Acceptance Criteria**:
1. `src/application/contracts/mappers.py` does not contain a function named `to_app_board_summary`.
2. `KanbanQueryHandlers.handle_list_boards()` does not call any function to map board summaries.
3. `KanbanQueryHandlers.handle_list_boards()` returns `self.repository.list_all()` directly.

#### Scenario: Query handler returns repository results without transformation

- Given: `KanbanQueryHandlers` wired with an in-memory repository containing two boards
- When: `handle_list_boards(ListBoardsQuery())` is called
- Then: the result is `list[AppBoardSummary]` with two elements
- And: no intermediate type conversion occurs between repository and handler return
