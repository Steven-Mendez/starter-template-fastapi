# query-card-lookup Specification

## Purpose
Ensure single-card query reads use direct card lookup and keep query handlers focused on orchestration through explicit query-port methods.

## Requirements

### Requirement: QCL-01 — Query-side card reads use direct lookup by `card_id`

**Priority**: High

The query-side repository port MUST expose a direct card lookup capability that reads a card by `card_id` without requiring a full board aggregate read.

**Acceptance Criteria**:
1. `KanbanQueryRepositoryPort` includes a method dedicated to direct card lookup by `card_id`.
2. The SQLModel query adapter implements that method with a direct `CardTable` read.
3. The direct lookup path does not require loading a board and iterating all columns/cards.

#### Scenario: Existing card is fetched by direct lookup

- Given: a persisted card exists with id `card-123`
- When: query-side card lookup is executed for `card-123`
- Then: the repository returns that card from a direct card read path
- And: the application returns the mapped `AppCard`

#### Scenario: Missing card returns not found semantics

- Given: no persisted card exists for id `card-missing`
- When: query-side card lookup is executed for `card-missing`
- Then: the repository returns `KanbanError.CARD_NOT_FOUND`
- And: the application layer maps that error to `ApplicationError.CARD_NOT_FOUND`

### Requirement: QCL-02 — `handle_get_card` orchestrates through query-port intent

**Priority**: High

`handle_get_card` MUST orchestrate through query-port methods that match read intent and avoid incidental board-level traversal logic.

**Acceptance Criteria**:
1. `handle_get_card` calls the direct lookup query-port method exactly once per request.
2. `handle_get_card` does not perform nested column/card scan loops.
3. Successful lookups preserve existing response shape and field mapping.
4. Not-found behavior remains equivalent to current API semantics (`404` via `ApplicationError.CARD_NOT_FOUND`).

#### Scenario: Handler avoids board hydration for card detail

- Given: a query repository implementation that can report method invocations
- When: `handle_get_card` executes for an existing card id
- Then: the direct card lookup method is invoked
- And: board detail lookup methods are not required for that read path
