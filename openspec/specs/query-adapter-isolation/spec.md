# query-adapter-isolation Specification

## Purpose
Ensure CQRS query handlers are isolated from command-side persistence capabilities by receiving a read-only adapter view.

## Requirements

### Requirement: QAI-01 - Query handlers are wired with a read-only adapter surface

**Priority**: High

Application dependency wiring MUST provide query handlers with an adapter that satisfies `KanbanQueryRepositoryPort` while not exposing command-write methods.

**Acceptance Criteria**:
1. Container wiring passes a query-only adapter object to `KanbanQueryHandlers`.
2. The query-only adapter delegates read methods to the underlying persistence repository.
3. The query-only adapter does not expose command methods such as `save`, `remove`, or `find_board_id_by_column`.

#### Scenario: Container builds split read and write dependency surfaces

- Given: runtime composition creates a repository used by command and query flows
- When: the application container builds `KanbanQueryHandlers`
- Then: `KanbanQueryHandlers.repository` is a query-only adapter
- And: command handlers continue using the existing unit-of-work plus repository path

#### Scenario: Query dependency does not expose mutations

- Given: query handlers resolved from container or test harness wiring
- When: query-side dependency surface is inspected
- Then: read methods (`list_all`, `find_by_id`, `find_card_by_id`, `find_board_id_by_card`) are available
- And: mutation methods (`save`, `remove`) are unavailable on the query dependency object

### Requirement: QAI-02 - Query behavior and public API remain unchanged

**Priority**: High

Introducing a query-only adapter MUST preserve existing query semantics and API contract behavior.

**Acceptance Criteria**:
1. Existing query handler behavior tests continue passing without response-shape changes.
2. Command handler behavior and write API endpoints remain unchanged.
3. No public API path or payload contract is modified by this isolation change.

#### Scenario: Existing CQRS route behavior remains stable

- Given: an existing board, column, and card created through command handlers
- When: query handlers execute board/card read use cases
- Then: query responses retain the prior data shape and values
- And: no additional command capabilities are required by query handlers
