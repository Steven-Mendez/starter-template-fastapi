# aggregate-encapsulation Specification

## Purpose
Ensure aggregate mutations are encapsulated behind domain intent methods so application handlers do not mutate board internals directly.

## Requirements

### Requirement: AEC-01 - Column creation uses board aggregate intent method

**Priority**: High

Application handlers MUST create board columns through a board domain intent method instead of direct mutation of `board.columns` internals.

**Acceptance Criteria**:
1. `handle_create_column` invokes a `Board` domain method (for example, `add_column`) to attach a new column.
2. `src/application/commands/column/create.py` contains no direct `board.columns.append(...)` mutation.
3. A unit test verifies column creation dispatches through the board domain method.

#### Scenario: Create column command mutates through board intent

- Given: an existing board with zero or more columns
- When: `handle_create_column` executes with a valid title
- Then: the handler adds the new column by calling a board domain method, not by appending directly to `board.columns`

### Requirement: AEC-02 - Column ordering semantics remain unchanged

**Priority**: High

Encapsulation changes MUST preserve current ordering behavior for board columns.

**Acceptance Criteria**:
1. New columns are still assigned `max(existing positions) + 1`.
2. The order of persisted columns remains append-to-end behavior after column creation.
3. Existing tests for column position and board detail ordering continue to pass unchanged.

#### Scenario: New column keeps tail position behavior

- Given: a board with existing columns at positions `0..n`
- When: a new column is created through the command handler
- Then: the new column position is `n + 1` and appears at the end of board column ordering
